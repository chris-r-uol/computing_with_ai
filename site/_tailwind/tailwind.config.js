/*
 * Tailwind configuration for the Computing with AI site.
 *
 * Built by scripts/build_tailwind.py into site/tailwind.css, which is
 * committed. Nothing here runs in a student's browser: the standalone Tailwind
 * CLI (via pytailwindcss) does the work once, on a developer's machine, and CI
 * rebuilds it to check the committed file has not drifted. The CDN build is
 * deliberately not used -- it would add a blocking third-party request to a
 * site that has to be readable from Chengdu on a poor connection.
 *
 * Two rules shape everything below:
 *
 * 1. `preflight: false`. Quarto's sidebar, table of contents, search,
 *    code highlighting and callouts all rest on Bootstrap. Tailwind's reset
 *    would fight it, and several accessibility behaviours are already tested
 *    against Bootstrap's markup.
 * 2. Colours are `var(--cwai-*)`, never literals. The one source of truth for
 *    the palette is site/styles.css, which tests/test_site.py reads to measure
 *    WCAG contrast. A colour written here as a hex value would be a second,
 *    unmeasured copy.
 *
 * `content` lists only committed, hand-authored files. site/data.qmd and
 * site/notebooks/ are generated at render time and are not scanned, so the
 * build output is a function of the repository alone -- which is what lets the
 * freshness check in CI be meaningful.
 */
module.exports = {
  content: ["./site/*.qmd", "./site/_stages/*.qmd"],
  // Every Tailwind utility is prefixed, and this is not cosmetic. Unprefixed,
  // Tailwind emits a utility for any word in the scanned content that happens
  // to name one -- and a lot of ordinary English about programming does:
  // "collapse", "table", "container", "block", "grid", "fixed", "visible",
  // "border". Several of those are also Bootstrap class names, and Tailwind's
  // stylesheet loads last. The first build of this site emitted `.collapse`
  // (visibility: collapse), which overrode Bootstrap's and hid the entire
  // sidebar on every page. The prefix makes that collision impossible, which
  // matters more here than the extra three characters, because the prose on
  // this site is going to keep growing.
  prefix: "cw-",
  // See rule 1 above.
  corePlugins: {
    preflight: false,
  },
  // Quarto writes the theme onto <body>, not <html>, and does not use
  // prefers-color-scheme at runtime: the toggle swaps this class.
  darkMode: ["selector", "body.quarto-dark"],
  theme: {
    extend: {
      colors: {
        bg: "var(--cwai-bg)",
        surface: "var(--cwai-surface)",
        ink: "var(--cwai-fg)",
        muted: "var(--cwai-muted)",
        link: "var(--cwai-link)",
        accent: "var(--cwai-accent)",
        "accent-fg": "var(--cwai-accent-fg)",
        "accent-soft": "var(--cwai-accent-soft)",
        "code-bg": "var(--cwai-code-bg)",
        "code-fg": "var(--cwai-code-fg)",
        edge: "var(--cwai-border)",
        focus: "var(--cwai-focus)",
        "callout-bg": "var(--cwai-callout-bg)",
      },
      fontFamily: {
        // Self-hosted nothing and fetched nothing: a web font would be either a
        // third-party request on the critical path or extra bytes, and this site
        // has to open quickly on a bad link from Chengdu. The CJK faces are
        // listed explicitly so the glossary's Chinese renders in a real CJK
        // face rather than in a Latin font's fallback glyphs.
        sans: [
          "-apple-system",
          "BlinkMacSystemFont",
          "Segoe UI",
          "Roboto",
          "Helvetica Neue",
          "Arial",
          "PingFang SC",
          "Hiragino Sans GB",
          "Microsoft YaHei",
          "Noto Sans CJK SC",
          "Noto Sans SC",
          "sans-serif",
        ],
        mono: [
          "ui-monospace",
          "SFMono-Regular",
          "SF Mono",
          "Menlo",
          "Consolas",
          "Liberation Mono",
          "monospace",
        ],
      },
      borderRadius: {
        card: "0.625rem",
      },
    },
  },
  plugins: [],
};
