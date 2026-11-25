"""Measure the rendered site's colour contrast and reflow in a real browser.

``site/accessibility.qmd`` publishes numbers: that every piece of visible text
meets its WCAG 2.2 AA contrast ratio against *the colour actually painted
behind it*, in both themes, and that no page needs sideways scrolling in a 640
or a 320 pixel window. Those numbers were first taken with a script typed into
a browser session, which left them unreproducible -- and that statement had
already been returned three times for claiming more than had been measured. So
the script lives here instead, and the numbers in the statement can be checked
by re-running it.

Why a browser at all, when ``tests/test_site.py`` already measures contrast:
that test reads the declared ``--cwai-*`` pairs out of ``site/styles.css``,
which is the weaker claim that the *palette* is sound. It cannot see which
colour a given paragraph ends up on. Text inherits its background from
whichever ancestor paints one, Bootstrap and the design layer both have
opinions about that, and only the cascade in a laid-out page settles it.
Reflow is the same kind of thing: ``min-width: 0`` on a grid item is invisible
from reading the CSS and decisive on a 320px screen.

What it does not do, so that the statement does not claim it: no keyboard walk
(that was done by hand), no screen reader, no text-only zoom, one browser
engine, and window-width emulation rather than real browser zoom.

Deliberately not wired into CI: it needs a browser binary, and the statement's
numbers are checked when a person reviews the statement, not on every push.

Usage:
    uv run python scripts/render_site.py
    uv run --with playwright python -m playwright install chromium
    uv run --with playwright python scripts/audit_site_a11y.py

    # Other options
    uv run --with playwright python scripts/audit_site_a11y.py \
        --site _site --widths 320 640 --json audit.json
"""

from __future__ import annotations

import argparse
import contextlib
import functools
import json
import sys
import threading
from collections.abc import Iterator, Sequence
from dataclasses import dataclass, field
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SITE = REPO_ROOT / "_site"
# 640px is a 1280px window at 200% zoom; 320px is 400%, the WCAG 1.4.10 width.
#
# 1280px is here for the contrast half rather than the reflow half. The navbar
# collapses into a toggle below 992px, so at 640 and 320 its items are
# `display: none` and the walk below skips them -- which meant the one surface
# on this site with its own palette, the dark bar, was never measured in a
# browser at all. Everything the bar carries is visible only at a desktop
# width, so a desktop width has to be in the run.
DEFAULT_WIDTHS = (1280, 640, 320)
VIEWPORT_HEIGHT = 900

# Quarto stores the reader's theme choice under this key: "default" is the
# first theme in `_quarto.yml`'s `theme:` map (light here) and "alternate" is
# the second. Setting it before the page loads is steadier than clicking the
# toggle, which lives in two places and is hidden in one of them at 320px.
#
# It is also why the pages are served over a loopback HTTP server rather than
# opened as file:// URLs: Quarto's own theme script skips localStorage entirely
# on a file URL, so a file:// run silently measures the light theme twice and
# reports "both themes". ``_assert_theme`` below would now catch that, and did.
THEME_SENTINEL = {"light": "default", "dark": "alternate"}

# A table that scrolls inside its own box is the one documented exception in
# the statement, and after the glossary was given back `display: table` the
# only such boxes left are Quarto's own code and code-output wrappers. An
# element inside one of these does not widen the page, so the page-level
# measurement below already excludes it; this list only labels the diagnostics.
SCROLLS_ITSELF = "pre, .cell-output, .sourceCode, .table-responsive"

# WCAG 1.4.3: 3:1 for large text (>=24px, or >=18.66px when bold), else 4.5:1.
MEASURE_CONTRAST = """
() => {
  const parse = (value) => {
    const n = value.match(/[\\d.]+/g);
    if (!n) return null;
    return {
      r: Number(n[0]), g: Number(n[1]), b: Number(n[2]),
      a: n.length > 3 ? Number(n[3]) : 1,
    };
  };
  const over = (top, bottom) => ({
    r: top.r * top.a + bottom.r * (1 - top.a),
    g: top.g * top.a + bottom.g * (1 - top.a),
    b: top.b * top.a + bottom.b * (1 - top.a),
    a: 1,
  });
  const luminance = (c) => {
    const [r, g, b] = [c.r, c.g, c.b].map((v) => {
      const s = v / 255;
      return s <= 0.03928 ? s / 12.92 : Math.pow((s + 0.055) / 1.055, 2.4);
    });
    return 0.2126 * r + 0.7152 * g + 0.0722 * b;
  };
  const ratio = (fg, bg) => {
    const pair = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
    return (pair[0] + 0.05) / (pair[1] + 0.05);
  };
  // The colour painted behind this text: climb until something is opaque,
  // compositing every translucent layer found on the way.
  const ground = (start) => {
    const layers = [];
    for (let node = start; node; node = node.parentElement) {
      const style = getComputedStyle(node);
      if (style.backgroundImage !== 'none') return { image: true };
      const colour = parse(style.backgroundColor);
      if (colour && colour.a > 0) {
        layers.push(colour);
        if (colour.a >= 1) break;
      }
    }
    let result = { r: 255, g: 255, b: 255, a: 1 };
    for (const layer of layers.reverse()) result = over(layer, result);
    return result;
  };
  const path = (el) => {
    const bits = [];
    for (let n = el; n && n !== document.body; n = n.parentElement) {
      bits.unshift(n.tagName.toLowerCase() + (n.id ? '#' + n.id : ''));
      if (bits.length >= 4) break;
    }
    return bits.join('>');
  };
  const skip = new Set(['SCRIPT', 'STYLE', 'NOSCRIPT', 'TEMPLATE', 'TITLE']);
  const measured = [];
  const failures = [];
  const unmeasurable = [];
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  for (let node = walker.nextNode(); node; node = walker.nextNode()) {
    const text = node.data.trim();
    if (!text) continue;
    const el = node.parentElement;
    if (!el || skip.has(el.tagName)) continue;
    const rect = el.getBoundingClientRect();
    // Zero-sized covers display:none anywhere above; 1px wide or tall is a
    // visually-hidden label, which a screen reader reads and nobody sees.
    if (rect.width < 2 || rect.height < 2) continue;
    const style = getComputedStyle(el);
    if (style.visibility !== 'visible' || Number(style.opacity) === 0) continue;
    const bg = ground(el);
    const sample = { text: text.slice(0, 60), where: path(el) };
    if (bg.image) { unmeasurable.push(sample); continue; }
    const fg = parse(style.color);
    if (!fg) { unmeasurable.push(sample); continue; }
    const size = parseFloat(style.fontSize);
    const weight = Number(style.fontWeight) || 400;
    const large = size >= 24 || (size >= 18.66 && weight >= 700);
    const required = large ? 3 : 4.5;
    const value = ratio(over(fg, bg), bg);
    measured.push(value);
    if (value + 0.005 < required) {
      failures.push({ ...sample, ratio: Math.round(value * 100) / 100,
                      required, size, weight,
                      colour: style.color, ground: JSON.stringify(bg) });
    }
  }
  const lowest = measured.length ? Math.min(...measured) : null;
  return {
    nodes: measured.length,
    lowest: lowest === null ? null : Math.round(lowest * 100) / 100,
    failures,
    unmeasurable,
  };
}
"""

MEASURE_REFLOW = """
(scrollsItself) => {
  const doc = document.documentElement;
  const overflow = doc.scrollWidth - doc.clientWidth;
  // Only reported when the page does overflow: these are the diagnostics, not
  // the test. The published claim is exactly the line above -- the document
  // needs no sideways scrolling -- and an element inside its own scroll box
  // never reaches it.
  const widest = [];
  if (overflow > 1) {
    for (const el of document.body.querySelectorAll('*')) {
      const rect = el.getBoundingClientRect();
      if (rect.width < 2 || rect.right <= doc.clientWidth + 1) continue;
      widest.push({
        where: el.tagName.toLowerCase() + (el.id ? '#' + el.id : ''),
        classes: (el.className || '').toString().slice(0, 80),
        right: Math.round(rect.right),
        inOwnScrollBox: el.closest(scrollsItself) !== null,
      });
    }
    widest.sort((a, b) => b.right - a.right);
  }
  return {
    clientWidth: doc.clientWidth,
    scrollWidth: doc.scrollWidth,
    overflow,
    widest: widest.slice(0, 8),
  };
}
"""


@dataclass
class Totals:
    """What the run measured, which is what the statement is allowed to claim."""

    pages: set[str] = field(default_factory=set)
    themes: set[str] = field(default_factory=set)
    widths: set[int] = field(default_factory=set)
    text_nodes: int = 0
    contrast_checks: int = 0
    reflow_checks: int = 0
    lowest_ratio: float | None = None
    contrast_failures: list[dict] = field(default_factory=list)
    reflow_failures: list[dict] = field(default_factory=list)
    unmeasurable: list[dict] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return not self.contrast_failures and not self.reflow_failures


@contextlib.contextmanager
def serve(site: Path) -> Iterator[str]:
    """Serve ``site`` on loopback and yield its base URL.

    Nothing leaves this machine: the handler is bound to 127.0.0.1 on a port
    the kernel picks, and the site fetches nothing from anywhere else -- which
    ``tests/test_site.py::test_pages_fetch_nothing_from_a_third_party`` is the
    standing proof of.
    """
    handler = functools.partial(_QuietHandler, directory=str(site))
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class _QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args) -> None:  # noqa: A003 - stdlib hook
        """One line per request would bury the measurements."""


def pages_of(site: Path) -> list[Path]:
    """Every rendered page, Quarto's bundled library pages excluded."""
    return sorted(
        page
        for page in site.rglob("*.html")
        if "site_libs" not in page.relative_to(site).parts
    )


def audit(site: Path, widths: Sequence[int], themes: Sequence[str]) -> Totals:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:  # pragma: no cover - documented above
        raise SystemExit(
            "playwright is not installed. This script is not part of the test "
            "dependencies; run it with:\n"
            "    uv run --with playwright python -m playwright install chromium\n"
            "    uv run --with playwright python scripts/audit_site_a11y.py"
        ) from exc

    pages = pages_of(site)
    if not pages:
        raise SystemExit(f"no rendered pages under {site}; run render_site.py first")

    totals = Totals(widths=set(widths), themes=set(themes))
    with serve(site) as base, sync_playwright() as play:
        browser = play.chromium.launch()
        try:
            for theme in themes:
                context = browser.new_context(
                    viewport={"width": max(widths), "height": VIEWPORT_HEIGHT}
                )
                sentinel = THEME_SENTINEL[theme]
                context.add_init_script(
                    f"window.localStorage.setItem('quarto-color-scheme', '{sentinel}')"
                )
                page = context.new_page()
                for path in pages:
                    name = path.relative_to(site).as_posix()
                    totals.pages.add(name)
                    for width in widths:
                        page.set_viewport_size(
                            {"width": width, "height": VIEWPORT_HEIGHT}
                        )
                        page.goto(f"{base}/{name}", wait_until="load")
                        _assert_theme(page, theme, name)
                        _record(totals, page, name, theme, width)
                context.close()
        finally:
            browser.close()
    return totals


def _assert_theme(page, theme: str, name: str) -> None:
    """Fail loudly rather than measure the light theme twice and say 'both'."""
    dark = page.evaluate("() => document.body.classList.contains('quarto-dark')")
    if dark != (theme == "dark"):
        raise SystemExit(
            f"{name}: asked for the {theme} theme but the page rendered the "
            "other one; the theme sentinel in this script is out of step with "
            "Quarto's"
        )


def _record(totals: Totals, page, name: str, theme: str, width: int) -> None:
    where = {"page": name, "theme": theme, "width": width}

    contrast = page.evaluate(MEASURE_CONTRAST)
    totals.text_nodes += contrast["nodes"]
    totals.contrast_checks += 1
    if contrast["lowest"] is not None:
        lowest = totals.lowest_ratio
        totals.lowest_ratio = (
            contrast["lowest"] if lowest is None else min(lowest, contrast["lowest"])
        )
    totals.contrast_failures += [where | f for f in contrast["failures"]]
    totals.unmeasurable += [where | u for u in contrast["unmeasurable"]]

    reflow = page.evaluate(MEASURE_REFLOW, SCROLLS_ITSELF)
    totals.reflow_checks += 1
    if reflow["overflow"] > 1:
        totals.reflow_failures.append(where | reflow)


def report(totals: Totals) -> None:
    print(
        f"{len(totals.pages)} pages x {len(sorted(totals.themes))} themes x "
        f"{len(totals.widths)} widths "
        f"({', '.join(sorted(totals.themes))}; "
        f"{', '.join(f'{w}px' for w in sorted(totals.widths, reverse=True))})"
    )
    print(
        f"contrast: {totals.text_nodes} visible text nodes measured against the "
        f"colour painted behind them, in {totals.contrast_checks} page views; "
        f"lowest ratio {totals.lowest_ratio}:1; "
        f"{len(totals.contrast_failures)} below the AA threshold"
    )
    print(
        f"reflow:   {totals.reflow_checks} page views measured; "
        f"{len(totals.reflow_failures)} needing sideways scrolling"
    )
    if totals.unmeasurable:
        print(
            f"note:     {len(totals.unmeasurable)} text nodes sat on a "
            "background image and could not be measured this way"
        )
    for failure in totals.contrast_failures:
        print(
            f"  FAIL contrast {failure['page']} [{failure['theme']}"
            f" {failure['width']}px] {failure['ratio']}:1 "
            f"(needs {failure['required']}:1) {failure['where']} "
            f"{failure['text']!r}"
        )
    for failure in totals.reflow_failures:
        print(
            f"  FAIL reflow {failure['page']} [{failure['theme']}"
            f" {failure['width']}px] document is {failure['scrollWidth']}px "
            f"wide in a {failure['clientWidth']}px window"
        )
        for element in failure["widest"]:
            print(
                f"       {element['where']} reaches {element['right']}px "
                f"(class {element['classes']!r}, in its own scroll box: "
                f"{element['inOwnScrollBox']})"
            )
    print("PASS" if totals.ok else "FAIL")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--site",
        type=Path,
        default=DEFAULT_SITE,
        help="the rendered site to measure (default: _site)",
    )
    parser.add_argument(
        "--widths",
        type=int,
        nargs="+",
        default=list(DEFAULT_WIDTHS),
        help="window widths in pixels (default: 640 320)",
    )
    parser.add_argument(
        "--themes",
        nargs="+",
        choices=sorted(THEME_SENTINEL),
        default=sorted(THEME_SENTINEL),
        help="themes to measure (default: both)",
    )
    parser.add_argument(
        "--json", type=Path, help="also write the full result to this file"
    )
    args = parser.parse_args(argv)

    totals = audit(args.site, args.widths, args.themes)
    report(totals)
    if args.json:
        args.json.write_text(
            json.dumps(
                {
                    "pages": sorted(totals.pages),
                    "themes": sorted(totals.themes),
                    "widths": sorted(totals.widths),
                    "text_nodes": totals.text_nodes,
                    "contrast_checks": totals.contrast_checks,
                    "reflow_checks": totals.reflow_checks,
                    "lowest_ratio": totals.lowest_ratio,
                    "contrast_failures": totals.contrast_failures,
                    "reflow_failures": totals.reflow_failures,
                    "unmeasurable": totals.unmeasurable,
                },
                indent=2,
            )
        )
        print(f"wrote {args.json}")
    return 0 if totals.ok else 1


if __name__ == "__main__":
    sys.exit(main())
