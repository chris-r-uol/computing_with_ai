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
        (licences / f"{name}.txt").write_text(f"{name} text")
    (tmp_path / "README.md").write_text("docs")
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
    (tree / "LICENSES" / "ODbL-1.0.txt").write_text("")
    problems = check_licences.audit(tree)
    assert any("ODbL-1.0.txt" in p for p in problems)


def test_licence_not_in_use_needs_no_text(tree):
    # generated and CC-BY-SA-4.0 have no file in LICENSES/ and that is fine.
    assert not (tree / "LICENSES" / "generated.txt").exists()
    assert not (tree / "LICENSES" / "CC-BY-SA-4.0.txt").exists()
    assert check_licences.audit(tree) == []


def test_documentation_is_not_treated_as_unclaimed_data(tree):
    (tree / "LICENSES" / "notes.txt").write_text("extra")
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
    text = (tmp_path / "README.md").read_text()
    for info in registry.list_datasets():
        assert info.title in text
        assert info.licence in text
        assert info.source_url in text
        assert info.attribution in text
        assert info.relpath in text


def test_data_readme_is_up_to_date():
    # Fails CI if the registry changed and the README was not regenerated.
    # Regenerate with: uv run python scripts/check_licences.py --write-readme
    committed = (registry.data_root() / "README.md").read_text()
    assert check_licences.readme_text() == committed
