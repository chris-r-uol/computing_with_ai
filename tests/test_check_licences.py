import check_licences
import pytest

from cwai import registry

BUDGET_BYTES = 80 * 1024 * 1024


@pytest.fixture
def tree(tmp_path):
    """A clean data tree: exactly the registered files plus licence texts."""
    for info in registry.list_datasets():
        path = tmp_path / info.relpath
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"x")
    licences = tmp_path / "LICENSES"
    licences.mkdir()
    for name in ("OGL-v3.0", "ODbL-1.0"):
        (licences / f"{name}.txt").write_text((f"{name} text"), encoding="utf-8")
    (tmp_path / "README.md").write_text(("docs"), encoding="utf-8")
    return tmp_path


def test_clean_tree_reports_no_problems(tree):
    assert check_licences.audit(tree) == []


def test_unclaimed_file_is_reported(tree):
    (tree / "stats19" / "mystery.parquet").write_bytes(b"x")
    problems = check_licences.audit(tree)
    assert any("mystery.parquet" in p for p in problems)


def test_missing_registered_file_is_reported(tree):
    (tree / "stats19" / "collisions.parquet").unlink()
    problems = check_licences.audit(tree)
    assert any("collisions" in p for p in problems)


def test_missing_licence_text_is_reported(tree):
    (tree / "LICENSES" / "OGL-v3.0.txt").unlink()
    problems = check_licences.audit(tree)
    assert any("OGL-v3.0.txt" in p for p in problems)


def test_empty_licence_text_is_reported(tree):
    (tree / "LICENSES" / "ODbL-1.0.txt").write_text((""), encoding="utf-8")
    problems = check_licences.audit(tree)
    assert any("ODbL-1.0.txt" in p for p in problems)


def test_licence_not_in_use_needs_no_text(tree):
    # generated and CC-BY-SA-4.0 have no file in LICENSES/ and that is fine.
    assert not (tree / "LICENSES" / "generated.txt").exists()
    assert not (tree / "LICENSES" / "CC-BY-SA-4.0.txt").exists()
    assert check_licences.audit(tree) == []


def test_documentation_is_not_treated_as_unclaimed_data(tree):
    (tree / "LICENSES" / "notes.txt").write_text(("extra"), encoding="utf-8")
    assert check_licences.audit(tree) == []


def test_total_size_over_budget_is_reported(tree):
    with (tree / "osm" / "leeds.gpkg").open("r+b") as f:
        f.truncate(BUDGET_BYTES + 1)
    problems = check_licences.audit(tree)
    assert any("80" in p for p in problems)


def test_total_size_under_budget_is_fine(tree):
    with (tree / "osm" / "leeds.gpkg").open("r+b") as f:
        f.truncate(BUDGET_BYTES - 1024)
    assert check_licences.audit(tree) == []


def test_empty_directory_reports_everything_missing(tmp_path):
    problems = check_licences.audit(tmp_path)
    assert len([p for p in problems if "missing" in p.lower()]) >= 8


def test_data_readme_documents_every_dataset(tmp_path):
    check_licences.write_readme(tmp_path)
    text = (tmp_path / "README.md").read_text(encoding="utf-8")
    for info in registry.list_datasets():
        assert info.title in text
        assert info.licence in text
        assert info.source_url in text
        assert info.attribution in text
        assert info.relpath in text


def test_data_readme_is_up_to_date():
    # Fails CI if the registry changed and the README was not regenerated.
    # Regenerate with: uv run python scripts/check_licences.py --write-readme
    committed = (registry.data_root() / "README.md").read_text(encoding="utf-8")
    assert check_licences.readme_text() == committed


def test_written_readme_is_utf8_regardless_of_locale(tmp_path):
    check_licences.write_readme(tmp_path)
    raw = (tmp_path / "README.md").read_bytes()
    assert "©".encode() in raw


def _attribution():
    return registry.get("network-leeds").attribution


def test_attribution_beside_odbl_output_is_accepted(tree):
    (tree / "osm" / "ATTRIBUTION.txt").write_text(
        _attribution() + "\n", encoding="utf-8"
    )
    assert check_licences.audit(tree) == []


def test_attribution_with_wrong_content_is_reported(tree):
    (tree / "osm" / "ATTRIBUTION.txt").write_text("Thanks, OSM!", encoding="utf-8")
    problems = check_licences.audit(tree)
    assert any("osm/ATTRIBUTION.txt" in p for p in problems)


def test_stray_attribution_elsewhere_is_still_reported(tree):
    (tree / "stats19" / "ATTRIBUTION.txt").write_text(_attribution(), encoding="utf-8")
    problems = check_licences.audit(tree)
    assert any(
        "stats19/ATTRIBUTION.txt" in p and "not registered" in p for p in problems
    )


def test_allow_missing_suppresses_only_the_missing_file_problem(tmp_path):
    # Empty tree: every dataset missing and every licence text missing.
    strict = check_licences.audit(tmp_path)
    relaxed = check_licences.audit(tmp_path, allow_missing=True)
    assert not any("is missing (dataset" in p for p in relaxed)
    assert any("is missing (dataset" in p for p in strict)
    # The licence-text check is still live.
    assert any("LICENSES/" in p for p in relaxed)


def test_allow_missing_still_reports_unclaimed_files(tree):
    (tree / "stats19" / "collisions.parquet").unlink()
    (tree / "mystery.parquet").write_bytes(b"x")
    problems = check_licences.audit(tree, allow_missing=True)
    assert any("mystery.parquet" in p for p in problems)
    assert not any("collisions" in p for p in problems)


def test_allow_missing_still_enforces_budget(tree):
    (tree / "big.bin").write_bytes(b"x" * BUDGET_BYTES)
    problems = check_licences.audit(tree, allow_missing=True)
    assert any("budget" in p for p in problems)


def test_main_flag_is_opt_in(monkeypatch, tmp_path, capsys):
    monkeypatch.setattr(check_licences.registry, "data_root", lambda: tmp_path)
    assert check_licences.main([]) == 1
    assert check_licences.main(["--allow-missing"]) == 1  # licences still absent
