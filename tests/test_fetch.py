import io
import json

import pytest

import fetch as fetch_module
from cwai.registry import YEARS
from fetch import SOURCES, fetch, record_provenance, sha256

NAME = "collisions-2021"


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


def test_sha256_is_stable_and_correct(tmp_path):
    p = tmp_path / "a.txt"
    p.write_bytes(b"hello")
    assert sha256(p) == sha256(p)
    assert sha256(p) == "2cf24dba5fb0a30e26e83b2ac5b9e29e1b161e5c1fa7425e73043362938b9824"


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

    monkeypatch.setattr(fetch_module.urllib.request, "urlopen", lambda *a, **k: Boom(b"x"))
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
