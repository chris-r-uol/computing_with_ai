import io
import json

import fetch as fetch_module
import pytest
from fetch import SOURCES, fetch, main, record_provenance, sha256

from cwai.registry import YEARS

NAME = "collisions-2021"
OSM_NAMES = ("west-yorkshire", "sichuan")


def _no_network(*args, **kwargs):
    raise AssertionError("network was touched")


class _FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def _serve(monkeypatch, payload: bytes):
    calls = []

    def fake(url, *a, **kw):
        assert kw.get("timeout"), "urlopen must be given a timeout"
        calls.append(url)
        return _FakeResponse(payload)

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", fake)
    return calls


def test_sources_cover_study_years_for_each_stats19_table():
    for table in ("collisions", "casualties", "vehicles"):
        for year in YEARS:
            assert f"{table}-{year}" in SOURCES
    assert "aadf" in SOURCES
    assert all(u.startswith("https://") for u in SOURCES.values())


def test_sources_cover_the_osm_extracts_build_osm_needs():
    # Fetched by hand once, which left them with no provenance entry and no
    # timeout; scripts/build_osm.py's docstring names these two keys.
    for name in OSM_NAMES:
        assert SOURCES[name].endswith("-latest.osm.pbf")


@pytest.fixture
def raw_in(tmp_path, monkeypatch):
    """Point raw_root() at a temporary directory."""
    monkeypatch.setattr(fetch_module.registry, "data_root", lambda: tmp_path / "data")
    return tmp_path / "raw"


def test_main_fetches_every_source_by_default(raw_in, monkeypatch, capsys):
    calls = _serve(monkeypatch, b"payload")
    assert main([]) == 0
    assert len(calls) == len(SOURCES)
    out = capsys.readouterr().out
    assert "total" in out
    assert out.count(" MB") == len(SOURCES) + 1  # one per file, plus the total


def test_main_fetches_only_the_named_sources(raw_in, monkeypatch, capsys):
    # The .pbf extracts are 164 MB; refreshing one CSV must not pull them.
    calls = _serve(monkeypatch, b"payload")
    assert main([NAME]) == 0
    assert calls == [SOURCES[NAME]]
    assert "west-yorkshire" not in capsys.readouterr().out


def test_main_passes_force_through(raw_in, monkeypatch):
    _serve(monkeypatch, b"old")
    main([NAME])
    calls = _serve(monkeypatch, b"new")
    assert main(["--force", NAME]) == 0
    assert calls == [SOURCES[NAME]]
    assert (raw_in / SOURCES[NAME].rsplit("/", 1)[-1]).read_bytes() == b"new"


def test_main_without_force_touches_no_network_for_present_files(raw_in, monkeypatch):
    _serve(monkeypatch, b"payload")
    main([NAME])
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    assert main([NAME]) == 0


def test_main_rejects_an_unknown_name_without_fetching(raw_in, monkeypatch, capsys):
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    assert main(["collisions-1066"]) == 2
    err = capsys.readouterr().err
    assert "collisions-1066" in err
    assert NAME in err  # the available names are listed


def test_main_rejects_an_unknown_flag(raw_in, monkeypatch, capsys):
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    assert main(["--all"]) == 2
    assert "--all" in capsys.readouterr().err


def test_main_list_prints_names_and_urls_without_fetching(raw_in, monkeypatch, capsys):
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    assert main(["--list"]) == 0
    out = capsys.readouterr().out
    for name, url in SOURCES.items():
        assert name in out and url in out
    assert not raw_in.exists()


def test_sha256_is_stable_and_correct(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"hello")
    assert sha256(p) == sha256(p)
    assert sha256(p) == (
        "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"
    )


def test_fetch_skips_existing_file_without_network(tmp_path, monkeypatch):
    target = tmp_path / SOURCES[NAME].rsplit("/", 1)[-1]
    target.write_bytes(b"already here")
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    result = fetch(NAME, tmp_path)
    assert result == target
    assert result.read_bytes() == b"already here"


def test_fetch_downloads_when_missing_and_records_provenance(tmp_path, monkeypatch):
    calls = _serve(monkeypatch, b"a,b\n1,2\n")
    path = fetch(NAME, tmp_path / "raw")
    assert path.read_bytes() == b"a,b\n1,2\n"
    assert calls == [SOURCES[NAME]]
    entry = json.loads((tmp_path / "raw" / "provenance.json").read_text())[path.name]
    assert entry["sha256"] == sha256(path)
    assert entry["url"] == SOURCES[NAME]
    assert not list((tmp_path / "raw").glob("*.part"))


def test_fetch_is_idempotent_after_a_completed_download(tmp_path, monkeypatch):
    _serve(monkeypatch, b"data")
    first = fetch(NAME, tmp_path)
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    assert fetch(NAME, tmp_path) == first


def test_fetch_force_redownloads(tmp_path, monkeypatch):
    _serve(monkeypatch, b"old")
    path = fetch(NAME, tmp_path)
    calls = _serve(monkeypatch, b"new")
    fetch(NAME, tmp_path, force=True)
    assert calls == [SOURCES[NAME]]
    assert path.read_bytes() == b"new"
    entry = json.loads((tmp_path / "provenance.json").read_text())[path.name]
    assert entry["sha256"] == sha256(path)


def test_failed_download_leaves_no_file_that_looks_complete(tmp_path, monkeypatch):
    class Boom(_FakeResponse):
        def read(self, *a):
            raise OSError("connection dropped")

    monkeypatch.setattr(
        fetch_module.urllib.request, "urlopen", lambda *a, **k: Boom(b"x")
    )
    with pytest.raises(OSError):
        fetch(NAME, tmp_path)
    assert not (tmp_path / SOURCES[NAME].rsplit("/", 1)[-1]).exists()

    _serve(monkeypatch, b"ok")
    assert fetch(NAME, tmp_path).read_bytes() == b"ok"


def test_unknown_source_name_raises(tmp_path):
    with pytest.raises(KeyError):
        fetch("nonsense", tmp_path)


def test_provenance_records_sha_and_timestamp(tmp_path):
    f = tmp_path / "a.txt"
    f.write_bytes(b"hello")
    manifest = tmp_path / "provenance.json"
    record_provenance(f, manifest)
    entry = json.loads(manifest.read_text())["a.txt"]
    assert {"sha256", "fetched_at"} <= entry.keys()
    assert entry["sha256"] == sha256(f)


def test_provenance_accumulates_across_calls(tmp_path):
    manifest = tmp_path / "provenance.json"
    for name in ("a.txt", "b.txt"):
        (tmp_path / name).write_bytes(name.encode())
        record_provenance(tmp_path / name, manifest)
    assert set(json.loads(manifest.read_text())) == {"a.txt", "b.txt"}


def test_interrupted_manifest_write_keeps_previous_record(tmp_path, monkeypatch):
    manifest = tmp_path / "provenance.json"
    (tmp_path / "a.txt").write_bytes(b"a")
    record_provenance(tmp_path / "a.txt", manifest)
    before = manifest.read_text()
    (tmp_path / "b.txt").write_bytes(b"b")

    def crash(self, target):
        raise OSError("disk full")

    monkeypatch.setattr(fetch_module.Path, "replace", crash)
    with pytest.raises(OSError):
        record_provenance(tmp_path / "b.txt", manifest)
    assert manifest.read_text() == before


def test_skip_path_records_provenance_for_present_unrecorded_file(
    tmp_path, monkeypatch
):
    target = tmp_path / SOURCES[NAME].rsplit("/", 1)[-1]
    target.write_bytes(b"arrived but never recorded")
    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", _no_network)
    fetch(NAME, tmp_path)
    entry = json.loads((tmp_path / "provenance.json").read_text())[target.name]
    assert entry["sha256"] == sha256(target)
    assert entry["url"] == SOURCES[NAME]
