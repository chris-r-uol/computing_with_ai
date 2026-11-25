# Computing with AI — Foundation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the repository, environment, data layer, self-check layer, CI and site shell that every notebook and widget in the module depends on.

**Architecture:** A single public repository containing a devcontainer, an installable teaching package `cwai`, vendored transport datasets described by a machine-readable registry, and a Quarto site rendered from the same notebooks students run in the Codespace. All dataset access goes through `cwai.data`, so a dataset supplied later drops in behind the same interface. All self-check answers live in one `checks/expected.json`, consumed by both the Python notebook helpers and (later) the site's JavaScript, so the two surfaces cannot disagree.

**Tech Stack:** Python 3.12, `uv`, pandas, pyarrow, geopandas, networkx, matplotlib, PyTorch, Keras 3/TensorFlow (CPU), pytest, ruff, nbclient, nbformat, Quarto, GitHub Actions, GitHub Pages, GitHub Codespaces.

**Spec:** `docs/superpowers/specs/2026-11-25-computing-with-ai-design.md`

## Global Constraints

- Python **3.12**. All dependencies pinned via `uv.lock`, committed.
- Target machine floor: **2-core, 8 GB Codespace, no GPU.** Every training example in stage 3 must complete in **under two minutes** on that machine.
- Total vendored data under `data/` must stay **under 80 MB**. Enforced by test.
- **All dataset access goes through `cwai.data`.** No notebook reads a path directly.
- **Fixes ship as new files, never as edits to a file a student may have modified.** A corrected notebook arrives as `NNb-...`.
- **Every notebook must run standalone**, independent of whether earlier notebooks were completed. Enforced by test.
- Student notebook renders must contain **no `solution`-tagged cell content**. Enforced by test.
- **Every exercise cell must carry at least a `nudge` and a `method` hint.** Enforced by test.
- Widgets (later plans) are **DOM/SVG, not Canvas**, and must meet **WCAG 2.2 AA** with a keyboard path and a text-equivalent view.
- Vendored imagery must contain **no identifiable people or vehicle registrations**.
- Allowed data licences: `OGL-v3.0`, `ODbL-1.0`, `CC-BY-SA-4.0`, `generated`. Any other value fails CI.
- Attribution strings are fixed copy: OGL sources carry `Contains public sector information licensed under the Open Government Licence v3.0.`; OSM-derived files carry `© OpenStreetMap contributors, licensed under the Open Database License (ODbL).`
- Study area: **West Yorkshire**. Years: **2021–2025** inclusive — the span DfT publishes as per-year STATS19 files. Provisional pending the module lead's decision (see ledger R20/R23); held as the single constant `cwai.registry.YEARS`.
- Material is in English.

## Review Focus

Failure modes the spec implies that no task's happy path exercises. Each has a test assigned to the task that owns the code.

1. **A notebook run standalone or out of order** — a student who skips ahead or returns months later must get a working notebook, not a `NameError` from a variable defined in an earlier one. *Test in Task 10.*
2. **A vendored data file missing or corrupt** — a beginner must get a sentence telling them what to do, not a bare `FileNotFoundError` traceback. *Test in Task 8.*
3. **A year or area not present in the vendored subset** — must raise listing what *is* available, never return an empty DataFrame that silently produces zeroes downstream. *Test in Task 8.*
4. **A notebook that errors during site render** — CI must fail and publish nothing, rather than deploying a page showing a traceback as if it were teaching material. *Test in Task 11.*
5. **`checks/expected.json` drifting from what consumers expect** — the Python helper and the site's JavaScript read the same file; a shape change that breaks one silently must fail CI. *Test in Task 9.*

---

### Task 1: Repository scaffolding, devcontainer and installable package

**Files:**
- Create: `pyproject.toml`, `.gitignore`, `README.md`, `.devcontainer/devcontainer.json`, `.devcontainer/postCreate.sh`, `ruff.toml`
- Create: `src/cwai/__init__.py`
- Test: `tests/test_package.py`

**Interfaces:**
- Consumes: nothing.
- Produces: installable package `cwai` with `cwai.__version__: str`. Dependency groups `core`, `dl`, `dev` declared in `pyproject.toml`; `dl` holds `torch` and `tensorflow` so CI jobs that do not need them install in seconds.

- [ ] **Step 1: `git init` and write the failing test**

```python
# tests/test_package.py
def test_package_imports_and_reports_version():
    import cwai
    assert isinstance(cwai.__version__, str)
    assert cwai.__version__
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_package.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cwai'`

- [ ] **Step 3: Write `pyproject.toml` and `src/cwai/__init__.py`**

`pyproject.toml`: `requires-python = ">=3.12,<3.13"`, hatchling build backend, `[tool.uv]` with dependency groups `core` (pandas, pyarrow, matplotlib, geopandas, pyogrio, networkx), `dl` (torch, tensorflow), `dev` (pytest, ruff, nbclient, nbformat, jsonschema). `src/cwai/__init__.py` sets `__version__ = "0.1.0"`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv sync --group dev && uv run pytest tests/test_package.py -v`
Expected: PASS

- [ ] **Step 5: Write the devcontainer**

`devcontainer.json`: Python 3.12 base image, `ghcr.io/devcontainers/features/python`, VS Code extensions `ms-toolsai.jupyter` and `GitHub.copilot` plus `GitHub.copilot-chat`, `postCreateCommand` running `.devcontainer/postCreate.sh`. The script runs `uv sync --all-groups` and `quarto --version` as a smoke check. Set `hostRequirements` to 2 cores / 8 GB so the declared floor matches the design.

- [ ] **Step 6: Create the notebook stage directories**

`notebooks/00-warmup/`, `01-foundations/`, `02-ai-accelerated/`, `03-machine-learning/`, `04-project/`, `90-stretch/`, each with a `.gitkeep`, so the structure the spec names exists before any notebook does and later plans have somewhere to land.

- [ ] **Step 7: Write `.gitignore` and `README.md`**

`.gitignore` must exclude `raw/` (downloaded source data, never committed), `.venv/`, `_site/`, `.quarto/`, `**/.ipynb_checkpoints`. `README.md` states what the module is, that the Codespace is the supported environment, and that local installation is unsupported.

- [ ] **Step 8: Commit**

```bash
git add pyproject.toml .gitignore README.md ruff.toml .devcontainer src tests notebooks
git commit -m "feat: repository scaffolding, devcontainer and cwai package"
```

---

### Task 2: Dataset registry

**Files:**
- Create: `src/cwai/registry.py`
- Test: `tests/test_registry.py`

**Interfaces:**
- Consumes: Task 1's package.
- Produces:
  - `DatasetInfo` frozen dataclass with fields `key: str`, `title: str`, `relpath: str`, `licence: str`, `attribution: str`, `source_url: str`, `description: str`.
  - `REGISTRY: dict[str, DatasetInfo]`
  - `get(key: str) -> DatasetInfo` — raises `UnknownDatasetError` listing available keys.
  - `list_datasets() -> list[DatasetInfo]` — sorted by key.
  - `UnknownDatasetError(KeyError)`
  - `ALLOWED_LICENCES: frozenset[str]`
  - `data_root() -> Path` — repository `data/` directory.
  - `AREA = "west-yorkshire"`, `YEARS = (2021, 2022, 2023, 2024, 2025)` — defined here, not in `scripts/`, because both `cwai.data` and the build scripts need them and the package must not import from `scripts/`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_registry.py
def test_every_entry_declares_licence_and_attribution():
    for info in registry.list_datasets():
        assert info.licence in registry.ALLOWED_LICENCES
        assert info.attribution.strip()
        assert info.source_url.strip()
        assert info.description.strip()

def test_keys_match_mapping_keys():
    for key, info in registry.REGISTRY.items():
        assert info.key == key

def test_get_unknown_key_lists_available_keys():
    with pytest.raises(registry.UnknownDatasetError) as exc:
        registry.get("no-such-dataset")
    assert "collisions" in str(exc.value)

def test_ogl_entries_carry_exact_attribution_string():
    expected = "Contains public sector information licensed under the Open Government Licence v3.0."
    for info in registry.list_datasets():
        if info.licence == "OGL-v3.0":
            assert info.attribution == expected
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_registry.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'cwai.registry'`

- [ ] **Step 3: Implement `src/cwai/registry.py`**

Populate `REGISTRY` with these keys: `collisions`, `casualties`, `vehicles` (all `OGL-v3.0`, source `https://www.data.gov.uk/dataset/cb7ae6f0-4be6-4935-9277-47e5ce24a11f/road-accidents-safety-data`); `traffic-counts` (`OGL-v3.0`, source `https://roadtraffic.dft.gov.uk/downloads`); `network-leeds`, `network-chengdu` (`ODbL-1.0`, source `https://www.openstreetmap.org/copyright`); `sensor-clean`, `sensor-faulty` (`generated`, source the in-repo generator path). `data_root()` resolves `data/` relative to the package location by walking up to the repository root.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_registry.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwai/registry.py tests/test_registry.py
git commit -m "feat: dataset registry with licence and attribution metadata"
```

---

### Task 3: Licence audit

**Files:**
- Create: `scripts/check_licences.py`, `data/LICENSES/OGL-v3.0.txt`, `data/LICENSES/ODbL-1.0.txt`
- Test: `tests/test_check_licences.py`

**Interfaces:**
- Consumes: `cwai.registry.list_datasets`, `cwai.registry.data_root`, `cwai.registry.ALLOWED_LICENCES`.
- Produces: `audit(data_dir: Path) -> list[str]` returning human-readable problems, empty when clean. `main() -> int` exits non-zero when problems exist.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_check_licences.py
def test_clean_tree_reports_no_problems(tmp_path):
    # tmp_path seeded with exactly the registry's relpaths plus LICENSES/
    assert audit(tmp_path) == []

def test_unclaimed_file_is_reported(tmp_path):
    (tmp_path / "stats19" / "mystery.parquet").write_bytes(b"x")
    problems = audit(tmp_path)
    assert any("mystery.parquet" in p for p in problems)

def test_missing_registered_file_is_reported(tmp_path):
    # remove one registered file from the seeded tree
    problems = audit(tmp_path)
    assert any("collisions" in p for p in problems)

def test_missing_licence_text_is_reported(tmp_path):
    # delete LICENSES/OGL-v3.0.txt
    problems = audit(tmp_path)
    assert any("OGL-v3.0.txt" in p for p in problems)

def test_total_size_over_budget_is_reported(tmp_path):
    # write a file exceeding the 80 MB budget
    problems = audit(tmp_path)
    assert any("80" in p for p in problems)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_check_licences.py -v`
Expected: FAIL — `scripts/check_licences.py` does not exist

- [ ] **Step 3: Implement `scripts/check_licences.py`**

`audit` checks four things: every file under `data_dir` except `README.md` and `LICENSES/**` is claimed by exactly one registry `relpath`; every registry `relpath` exists; `LICENSES/<licence>.txt` exists for every non-`generated` licence in use; total size of `data_dir` is under 80 MB. Fetch the two licence texts from the National Archives and OpenStreetMap respectively and commit them.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_check_licences.py -v`
Expected: PASS

- [ ] **Step 5: Write the failing test for the generated data README**

```python
def test_data_readme_documents_every_dataset(tmp_path):
    write_readme(tmp_path)
    text = (tmp_path / "README.md").read_text()
    for info in registry.list_datasets():
        assert info.title in text
        assert info.licence in text
        assert info.source_url in text

def test_data_readme_is_up_to_date():
    # fails CI if the registry changed and the README was not regenerated
    assert readme_text() == (registry.data_root() / "README.md").read_text()
```

- [ ] **Step 6: Implement `write_readme(data_dir: Path) -> None` and `readme_text() -> str` in `scripts/check_licences.py`**

The spec makes `data/README.md` teaching material as well as paperwork, so it is generated from the registry rather than hand-written: provenance, licence and attribution per source, plus a short note on why licence hygiene matters in transport research.

- [ ] **Step 7: Run tests to verify they pass**

Run: `uv run pytest tests/test_check_licences.py -v`
Expected: PASS

- [ ] **Step 8: Commit**

```bash
git add scripts/check_licences.py data/LICENSES data/README.md tests/test_check_licences.py
git commit -m "feat: licence audit, data budget and generated data README"
```

---

### Task 4: Raw data fetchers

**Files:**
- Create: `scripts/fetch.py`
- Test: `tests/test_fetch.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `SOURCES: dict[str, str]` mapping a source name to its download URL.
  - `fetch(name: str, dest_dir: Path, force: bool = False) -> Path` — downloads, skips when the file is already present and `force` is false, records SHA-256 in `dest_dir / "provenance.json"`.
  - `record_provenance(path: Path, manifest: Path) -> None`
  - `sha256(path: Path) -> str`

Downloads go to `raw/`, which is gitignored. Vendored subsets are built from `raw/` in Task 5.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_fetch.py
def test_sha256_is_stable(tmp_path):
    p = tmp_path / "a.txt"; p.write_bytes(b"hello")
    assert sha256(p) == sha256(p)

def test_fetch_skips_existing_file_without_network(tmp_path, monkeypatch):
    # pre-create the target; monkeypatch urlopen to raise if called
    assert fetch("collisions", tmp_path).exists()

def test_fetch_force_redownloads(tmp_path, monkeypatch):
    # monkeypatch urlopen to serve bytes from a local fixture; assert it was called
    ...

def test_provenance_records_url_sha_and_timestamp(tmp_path):
    manifest = tmp_path / "provenance.json"
    record_provenance(tmp_path / "a.txt", manifest)
    entry = json.loads(manifest.read_text())["a.txt"]
    assert {"sha256", "fetched_at"} <= entry.keys()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `scripts/fetch.py`**

Use `urllib.request` rather than adding a dependency. `SOURCES` holds the STATS19 collision, casualty and vehicle CSVs from `https://data.dft.gov.uk/road-accidents-safety-data/` and the DfT AADF counts from `https://roadtraffic.dft.gov.uk/downloads`. Network access appears only inside `fetch`, so every test above runs offline.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_fetch.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/fetch.py tests/test_fetch.py
git commit -m "feat: raw data fetchers with provenance recording"
```

---

### Task 5: Tabular subset builder

**Files:**
- Create: `scripts/build_subsets.py`
- Test: `tests/test_build_subsets.py`, `tests/fixtures/stats19_collisions_sample.csv`, `tests/fixtures/dft_counts_sample.csv`

**Interfaces:**
- Consumes: `scripts/fetch.py` output layout; `cwai.registry.AREA` and `cwai.registry.YEARS`.
- Produces:
  - `COLLISION_COLUMNS: tuple[str, ...]` — the pruned column set, including `accident_index`, `accident_year`, `longitude`, `latitude`, `accident_severity`, `number_of_vehicles`, `number_of_casualties`, `date`, `day_of_week`, `time`, `local_authority_ons_district`, `road_type`, `speed_limit`, `light_conditions`, `weather_conditions`, `road_surface_conditions`.
  - `build_collisions(raw_csv: Path, out: Path) -> pd.DataFrame`
  - `build_casualties(raw_csv: Path, out: Path) -> pd.DataFrame`
  - `build_vehicles(raw_csv: Path, out: Path) -> pd.DataFrame`
  - `build_counts(raw_csv: Path, out: Path) -> pd.DataFrame`
  - Each writes Parquet and returns the frame.

Severity is kept as the raw integer code plus an ordered categorical `severity_label` with values `Fatal`, `Serious`, `Slight`, because the design's stage 1 asks students to notice that a coded field needs a lookup.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build_subsets.py
def test_collisions_keeps_only_target_area_and_years(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert set(df.accident_year) <= set(YEARS)
    assert df.local_authority_ons_district.str.startswith("E08").all()

def test_collisions_columns_exactly_match_declared_set(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert tuple(df.columns) == COLLISION_COLUMNS + ("severity_label",)

def test_severity_label_is_ordered_categorical(tmp_path):
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert list(df.severity_label.cat.categories) == ["Fatal", "Serious", "Slight"]
    assert df.severity_label.cat.ordered

def test_parquet_roundtrips_dtypes(tmp_path):
    out = tmp_path / "c.parquet"
    df = build_collisions(FIXTURE, out)
    assert pd.read_parquet(out).dtypes.to_dict() == df.dtypes.to_dict()

def test_implausible_coordinates_are_dropped_not_zeroed(tmp_path):
    # fixture contains a row at lon=0, lat=0
    df = build_collisions(FIXTURE, tmp_path / "c.parquet")
    assert not ((df.longitude == 0) & (df.latitude == 0)).any()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_subsets.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Hand-write the CSV fixtures**

Each fixture carries 30–40 rows: in-area and out-of-area, in-range and out-of-range years, one row at `lon=0, lat=0`, one row with a missing severity, and at least one of each severity code. These fixtures are the only place the plan fixes data values, and later tasks assert against them.

- [ ] **Step 4: Implement `scripts/build_subsets.py`**

West Yorkshire is selected by the five ONS district codes for Leeds, Bradford, Kirklees, Calderdale and Wakefield. Severity codes map `1 -> Fatal`, `2 -> Serious`, `3 -> Slight`.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_subsets.py -v`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add scripts/build_subsets.py tests/test_build_subsets.py tests/fixtures
git commit -m "feat: STATS19 and DfT counts subset builders"
```

---

### Task 6: OSM network extracts

**Files:**
- Create: `scripts/build_osm.py`
- Test: `tests/test_build_osm.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `BBOXES: dict[str, tuple[float, float, float, float]]` with `leeds = (-1.62, 53.75, -1.46, 53.84)` and `chengdu = (103.95, 30.60, 104.15, 30.72)`, each `(min_lon, min_lat, max_lon, max_lat)`.
  - `clip(gdf: gpd.GeoDataFrame, bbox: tuple[float, float, float, float]) -> gpd.GeoDataFrame`
  - `build_network(pbf: Path, place: str, out: Path) -> gpd.GeoDataFrame` — writes GeoPackage with layers `edges` and `stations`.
  - `HIGHWAY_KEEP: frozenset[str]` — `motorway`, `trunk`, `primary`, `secondary`, `tertiary`, `residential`, `cycleway`, `footway`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_build_osm.py
def test_clip_keeps_inside_drops_outside():
    # synthetic GeoDataFrame: one LineString inside the Leeds bbox, one in Cornwall
    assert len(clip(gdf, BBOXES["leeds"])) == 1

def test_clip_preserves_crs():
    assert clip(gdf, BBOXES["leeds"]).crs == gdf.crs

def test_output_has_edges_and_stations_layers(tmp_path):
    # built from a tiny hand-made GeoPackage fixture rather than a real .pbf
    assert {l for l, _ in pyogrio.list_layers(out)} == {"edges", "stations"}

def test_attribution_written_alongside_output(tmp_path):
    assert "OpenStreetMap contributors" in (tmp_path / "ATTRIBUTION.txt").read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_build_osm.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `scripts/build_osm.py`**

Source `.pbf` extracts from Geofabrik are fetched manually into `raw/` and documented in the script's docstring; the script itself takes a path, so no test touches the network. Keep only `HIGHWAY_KEEP` ways and nodes tagged `railway=station` or `station=subway`. Write `ATTRIBUTION.txt` next to each output with the exact ODbL string from the global constraints.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_build_osm.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/build_osm.py tests/test_build_osm.py
git commit -m "feat: OSM network extracts for Leeds and Chengdu"
```

---

### Task 7: Synthetic data generators

**Files:**
- Create: `scripts/make_synthetic.py`
- Test: `tests/test_make_synthetic.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `SEED = 20261125`
  - `make_sensor_series(days: int = 365, faults: tuple[str, ...] = (), seed: int = SEED) -> pd.DataFrame` — hourly flow for one count site; columns `timestamp`, `flow`, `sensor_id`.
  - `FAULTS: frozenset[str]` — `overnight_dropout`, `shift_midyear`, `stuck_sensor`
  - `make_leaky_split(df: pd.DataFrame, seed: int = SEED) -> tuple[pd.DataFrame, pd.DataFrame]` — a deliberately contaminated train/test split for the leakage lesson.
  - `UnknownFaultError(ValueError)`

The clean series carries a realistic weekday morning and evening peak, a weekend profile, and mild noise, so a student can see structure before they see faults.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_make_synthetic.py
def test_same_seed_gives_identical_output():
    assert make_sensor_series(days=30).equals(make_sensor_series(days=30))

def test_clean_series_has_no_missing_flow():
    assert make_sensor_series(days=30).flow.notna().all()

def test_weekday_morning_peak_exceeds_small_hours():
    df = make_sensor_series(days=60)
    hourly = df.groupby(df.timestamp.dt.hour).flow.mean()
    assert hourly[8] > hourly[3] * 2

def test_overnight_dropout_nulls_only_night_hours():
    df = make_sensor_series(days=30, faults=("overnight_dropout",))
    missing_hours = set(df[df.flow.isna()].timestamp.dt.hour)
    assert missing_hours and missing_hours <= {0, 1, 2, 3, 4}

def test_shift_midyear_changes_mean_across_halves():
    df = make_sensor_series(days=365, faults=("shift_midyear",))
    first, second = df.flow[:len(df)//2].mean(), df.flow[len(df)//2:].mean()
    assert abs(second - first) > first * 0.2

def test_unknown_fault_lists_available_faults():
    with pytest.raises(UnknownFaultError) as exc:
        make_sensor_series(faults=("not-a-fault",))
    assert "overnight_dropout" in str(exc.value)

def test_leaky_split_shares_timestamps_between_train_and_test():
    train, test = make_leaky_split(make_sensor_series(days=60))
    assert set(train.timestamp) & set(test.timestamp)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_make_synthetic.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `scripts/make_synthetic.py`**

Build the profile as a base level plus two Gaussian peaks at 08:00 and 17:00 on weekdays, a flatter single-peak weekend profile, then multiplicative noise from a seeded `numpy.random.default_rng`. Faults are applied as post-processing passes so they compose. Write `data/synthetic/sensor-clean.parquet` and `sensor-faulty.parquet` under `__main__`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_make_synthetic.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add scripts/make_synthetic.py tests/test_make_synthetic.py
git commit -m "feat: seeded synthetic sensor series with planted faults"
```

---

### Task 8: Data loaders

**Files:**
- Create: `src/cwai/data.py`
- Test: `tests/test_data.py`

**Interfaces:**
- Consumes: `cwai.registry.get`, `cwai.registry.data_root`, `cwai.registry.UnknownDatasetError`.
- Produces:
  - `load_collisions(years: Sequence[int] | None = None) -> pd.DataFrame`
  - `load_casualties(years: Sequence[int] | None = None) -> pd.DataFrame`
  - `load_vehicles(years: Sequence[int] | None = None) -> pd.DataFrame`
  - `load_traffic_counts(years: Sequence[int] | None = None) -> pd.DataFrame`
  - `load_network(place: str = "leeds", layer: str = "edges") -> gpd.GeoDataFrame`
  - `load_sensor_series(variant: str = "clean") -> pd.DataFrame`
  - `available_years(key: str) -> list[int]`
  - `describe(key: str) -> str` — title, licence, attribution and row count, for students to print.
  - `MissingDataError(FileNotFoundError)`, `YearNotAvailableError(ValueError)`

Every error message must name the problem and the next action in plain English, because a beginner reads the last line of a traceback and nothing else.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_data.py
def test_load_collisions_returns_all_years_by_default():
    assert set(load_collisions().accident_year) == set(YEARS)

def test_load_collisions_filters_to_requested_years():
    assert set(load_collisions(years=[2022]).accident_year) == {2022}

def test_requesting_absent_year_raises_and_lists_available(monkeypatch):
    with pytest.raises(YearNotAvailableError) as exc:
        load_collisions(years=[1999])
    assert "2021" in str(exc.value) and "1999" in str(exc.value)

def test_requesting_absent_year_does_not_return_empty_frame():
    # guards Review Focus 3: silent empties propagate as zeroes
    with pytest.raises(YearNotAvailableError):
        load_collisions(years=[1999])

def test_missing_file_raises_actionable_message(monkeypatch, tmp_path):
    monkeypatch.setattr(registry, "data_root", lambda: tmp_path)
    with pytest.raises(MissingDataError) as exc:
        load_collisions()
    msg = str(exc.value)
    assert "collisions" in msg
    assert "scripts/build_subsets.py" in msg

def test_unknown_network_place_lists_available_places():
    with pytest.raises(registry.UnknownDatasetError) as exc:
        load_network(place="paris")
    assert "leeds" in str(exc.value) and "chengdu" in str(exc.value)

def test_describe_includes_licence_and_attribution():
    text = describe("collisions")
    assert "Open Government Licence" in text

def test_sensor_variants_differ():
    assert load_sensor_series("clean").flow.isna().sum() == 0
    assert load_sensor_series("faulty").flow.isna().sum() > 0
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_data.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `src/cwai/data.py`**

A single private `_read(key)` resolves the registry entry, checks the file exists, and raises `MissingDataError` naming the dataset and the script that rebuilds it. Year filtering is shared by the four tabular loaders and raises `YearNotAvailableError` before filtering, never after.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_data.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwai/data.py tests/test_data.py
git commit -m "feat: dataset loaders with beginner-readable errors"
```

---

### Task 9: Self-check layer

**Files:**
- Create: `src/cwai/checks.py`, `checks/expected.json`, `checks/expected.schema.json`
- Test: `tests/test_checks.py`

**Interfaces:**
- Consumes: nothing from earlier tasks.
- Produces:
  - `check(name: str, value: object) -> CheckResult`
  - `CheckResult` frozen dataclass with `name: str`, `passed: bool`, `message: str`; `__repr__` renders a student-facing line (`✓ passed` / `✗` plus what differed). Truthiness follows `passed`.
  - `expect_columns(df, columns: Iterable[str]) -> None`
  - `expect_shape(df, rows: int | None = None, cols: int | None = None) -> None`
  - `UnknownCheckError(KeyError)`, `CheckFailed(AssertionError)`
  - `load_expected(path: Path | None = None) -> dict`
  - `TOLERANCE = 1e-6`

`checks/expected.json` is the single source of truth for self-check answers and is read by the site's JavaScript in a later plan. Its shape is pinned by `expected.schema.json`: an object mapping check name to `{"type": "number"|"string"|"list"|"shape", "value": ..., "tolerance": number?}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_checks.py
def test_passing_numeric_check_is_truthy():
    assert check("demo-number", 42)

def test_failing_numeric_check_reports_both_values():
    result = check("demo-number", 41)
    assert not result.passed
    assert "41" in result.message and "42" in result.message

def test_numeric_check_respects_tolerance():
    assert check("demo-float", 0.1 + 0.2)

def test_unknown_check_name_lists_nearby_names():
    with pytest.raises(UnknownCheckError) as exc:
        check("demo-numbr", 42)
    assert "demo-number" in str(exc.value)

def test_expect_columns_names_the_missing_column():
    with pytest.raises(CheckFailed) as exc:
        expect_columns(pd.DataFrame({"a": [1]}), ["a", "b"])
    assert "b" in str(exc.value)

def test_expected_json_validates_against_schema():
    jsonschema.validate(load_expected(), json.loads(SCHEMA.read_text()))

def test_every_expected_entry_has_a_supported_type():
    # guards Review Focus 5: a shape the JS consumer cannot read must fail CI
    for entry in load_expected().values():
        assert entry["type"] in {"number", "string", "list", "shape"}
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_checks.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `src/cwai/checks.py` and seed `checks/expected.json`**

Seed with `demo-number` (42) and `demo-float` (0.3, tolerance 1e-6) only; real entries arrive with the notebooks that use them. Unknown-name suggestions use `difflib.get_close_matches`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_checks.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add src/cwai/checks.py checks tests/test_checks.py
git commit -m "feat: self-check layer shared by notebooks and site"
```

---

### Task 10: Notebook execution harness and CI

**Files:**
- Create: `scripts/run_notebooks.py`, `.github/workflows/tests.yml`, `.github/workflows/notebooks.yml`
- Create: `notebooks/01-foundations/00-smoke.ipynb`
- Test: `tests/test_run_notebooks.py`, `tests/fixtures/broken.ipynb`, `tests/fixtures/depends_on_earlier.ipynb`

**Interfaces:**
- Consumes: `cwai.data` (the smoke notebook imports it).
- Produces:
  - `run(path: Path, timeout: int = 120) -> NotebookResult`
  - `NotebookResult` frozen dataclass with `path: Path`, `passed: bool`, `seconds: float`, `error: str | None`
  - `run_all(root: Path, timeout: int = 120) -> list[NotebookResult]` — sorted by path.
  - `TIMEOUT_SECONDS = 120` — matches the design's two-minute ceiling.

Each notebook is executed in a fresh kernel with `cwd` set to the repository root, which is what makes the isolation guarantee real rather than aspirational.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_run_notebooks.py
def test_broken_notebook_is_reported_not_raised():
    result = run(FIXTURES / "broken.ipynb")
    assert not result.passed
    assert "NameError" in result.error

def test_notebook_depending_on_earlier_state_fails_in_isolation():
    # guards Review Focus 1: a fresh kernel must expose the hidden dependency
    assert not run(FIXTURES / "depends_on_earlier.ipynb").passed

def test_smoke_notebook_passes_within_timeout():
    result = run(REPO / "notebooks/01-foundations/00-smoke.ipynb")
    assert result.passed
    assert result.seconds < TIMEOUT_SECONDS

def test_run_all_returns_one_result_per_notebook(tmp_path):
    assert len(run_all(FIXTURES)) == len(list(FIXTURES.glob("*.ipynb")))
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_run_notebooks.py -v`
Expected: FAIL — module missing

- [ ] **Step 3: Implement `scripts/run_notebooks.py`**

Use `nbclient.NotebookClient` with `allow_errors=False`. Catch `CellExecutionError` and put its message in `error` rather than propagating, so one bad notebook does not hide the rest.

- [ ] **Step 4: Write the smoke notebook and the two fixtures**

`00-smoke.ipynb` loads collisions through `cwai.data`, prints `describe("collisions")` and asserts the frame is non-empty — it proves the whole stack from devcontainer to data in one cell, and is the first thing a student runs. `broken.ipynb` references an undefined name. `depends_on_earlier.ipynb` uses a variable no cell in it defines.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_run_notebooks.py -v`
Expected: PASS

- [ ] **Step 6: Write the CI workflows**

`tests.yml` on push and pull request: `uv sync --group dev --group core`, `uv run ruff check`, `uv run pytest`, `uv run python scripts/check_licences.py`. `notebooks.yml` on push, pull request and weekly schedule: `uv sync --all-groups`, then `uv run python scripts/run_notebooks.py notebooks/` failing non-zero on any failure or timeout. The weekly run is what catches a dependency drifting under material nobody has touched for months, which the design's always-available requirement needs.

- [ ] **Step 7: Verify CI passes**

Run: `gh workflow run tests.yml && gh run watch`
Expected: both workflows green

- [ ] **Step 8: Commit**

```bash
git add scripts/run_notebooks.py .github/workflows notebooks tests/test_run_notebooks.py tests/fixtures
git commit -m "feat: notebook execution harness and CI"
```

---

### Task 11: Quarto site shell and Pages deployment

**Files:**
- Create: `site/_quarto.yml`, `site/index.qmd`, `site/accessibility.qmd`, `site/glossary.qmd`, `site/styles.css`, `scripts/render_site.py`, `.github/workflows/site.yml`
- Test: `tests/test_site.py`

**Interfaces:**
- Consumes: `notebooks/` (rendered as site content), `cwai.registry.list_datasets` (the data page is generated from the registry).
- Produces:
  - a rendered site in `_site/`; `site/data.qmd` generated at render time listing every dataset with licence and attribution.
  - `render(site_dir: Path, out_dir: Path, notebooks: Sequence[Path] | None = None) -> subprocess.CompletedProcess` in `scripts/render_site.py` — wraps `quarto render`, returning the completed process rather than raising, so a failing render is assertable. `notebooks` restricts the render to a subset, which is how the broken-notebook test stays fast.
  - `SITE_OUT = Path("_site")`

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_site.py
def test_render_fails_when_a_notebook_errors(tmp_path):
    # guards Review Focus 4: a broken notebook must not reach a published page
    assert render(tmp_path, notebooks=[FIXTURES / "broken.ipynb"]).returncode != 0

def test_rendered_site_contains_no_solution_cell_content():
    html = (SITE_OUT / "notebooks/01-foundations/00-smoke.html").read_text()
    assert "CWAI-SOLUTION" not in html

def test_data_page_lists_every_registered_dataset():
    html = (SITE_OUT / "data.html").read_text()
    for info in registry.list_datasets():
        assert info.title in html

def test_data_page_carries_required_attribution_strings():
    html = (SITE_OUT / "data.html").read_text()
    assert "Open Government Licence v3.0" in html
    assert "OpenStreetMap contributors" in html

def test_every_page_declares_a_language():
    for page in SITE_OUT.rglob("*.html"):
        assert 'lang="en"' in page.read_text()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_site.py -v`
Expected: FAIL — site does not exist

- [ ] **Step 3: Write the Quarto project**

`_quarto.yml`: `project.type: website`, `execute.freeze: auto` so CI does not re-run every notebook on every render, sidebar navigation grouped by the design's four stages plus stretch, `theme` with a light and a dark variant, `toc: true`. `styles.css` must meet WCAG 2.2 AA contrast in both themes. `index.qmd` states the two routes through the material — Codespace-first and site-first — because goal 6 depends on students knowing both exist.

- [ ] **Step 4: Write `accessibility.qmd` and the glossary stub**

`accessibility.qmd` is the published accessibility statement the design's section 7.9 requires. `glossary.qmd` holds the bilingual table, seeded with the twenty terms stage 1 needs and marked as growing with the material.

- [ ] **Step 5: Run tests to verify they pass**

Run: `quarto render site && uv run pytest tests/test_site.py -v`
Expected: PASS

- [ ] **Step 6: Write `.github/workflows/site.yml`**

On push to the default branch: `uv sync --all-groups`, `quarto render site`, upload `_site/` as a Pages artifact, deploy. The job must depend on `tests.yml` succeeding, so a failing notebook blocks publication.

- [ ] **Step 7: Verify deployment**

Run: `gh run watch` after pushing, then confirm the published URL serves `index.html` and `data.html`.
Expected: site live on GitHub Pages

- [ ] **Step 8: Commit**

```bash
git add site .github/workflows/site.yml tests/test_site.py
git commit -m "feat: Quarto site shell with Pages deployment"
```

---

### Task 12: Solution stripping and hint tooling

**Files:**
- Create: `scripts/build_student_notebooks.py`, `hints/README.md`, `hints/01-foundations.yml`
- Test: `tests/test_student_notebooks.py`, `tests/test_hints.py`

**Interfaces:**
- Consumes: `notebooks/` source tree.
- Produces:
  - `SOLUTION_TAG = "solution"`, `EXERCISE_TAG = "exercise"`, `STUB_MARKER = "# your code here"`
  - `strip_solutions(nb: nbformat.NotebookNode) -> nbformat.NotebookNode` — replaces each solution cell's source with `STUB_MARKER`, preserving tags.
  - `build(src_root: Path, out_root: Path) -> list[Path]`
  - `exercise_ids(nb) -> list[str]` — from each exercise cell's `metadata.cwai.id`.
  - `load_hints(path: Path) -> dict[str, dict[str, str]]` — exercise id to tier name to text.
  - `HINT_TIERS = ("nudge", "method", "code")`
  - `validate_hints(hints: dict[str, dict[str, str]], exercise_ids: Sequence[str]) -> None` — raises `MissingHintError` naming the exercise and the missing or unrecognised tier.
  - `hints_file_for(notebook_path: Path) -> Path` — maps `notebooks/<stage>/<name>.ipynb` to `hints/<stage>.yml`.
  - `MissingHintError(ValueError)`

Authoring happens in the full notebooks; student notebooks are generated, never hand-maintained.

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_student_notebooks.py
def test_solution_cells_are_replaced_with_stub():
    out = strip_solutions(nb_with_solution())
    assert out.cells[1].source.strip() == STUB_MARKER

def test_tags_are_preserved_so_rebuilds_are_idempotent():
    once = strip_solutions(nb_with_solution())
    assert strip_solutions(once).cells[1].source.strip() == STUB_MARKER

def test_non_solution_cells_are_untouched():
    nb = nb_with_solution()
    assert strip_solutions(nb).cells[0].source == nb.cells[0].source

# tests/test_hints.py
def test_every_exercise_has_nudge_and_method():
    for nb_path in REPO.glob("notebooks/**/*.ipynb"):
        hints = load_hints(hints_file_for(nb_path))
        for ex_id in exercise_ids(nbformat.read(nb_path, as_version=4)):
            assert {"nudge", "method"} <= hints[ex_id].keys()

def test_missing_hint_names_the_exercise_and_tier():
    with pytest.raises(MissingHintError) as exc:
        validate_hints({"ex-1": {"nudge": "look here"}}, ["ex-1"])
    assert "ex-1" in str(exc.value) and "method" in str(exc.value)

def test_hint_tiers_are_restricted_to_known_names():
    with pytest.raises(MissingHintError):
        validate_hints({"ex-1": {"nudge": "a", "method": "b", "answer": "c"}}, ["ex-1"])
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `uv run pytest tests/test_student_notebooks.py tests/test_hints.py -v`
Expected: FAIL — modules missing

- [ ] **Step 3: Implement `scripts/build_student_notebooks.py`**

Solution cell sources are wrapped in a `CWAI-SOLUTION` comment marker in the full notebooks, which is what Task 11's render test greps for — so a stripping bug fails the site test too, not only this one.

- [ ] **Step 4: Write `hints/README.md` and the stage 1 hints file**

`README.md` documents the three tiers and states the rule from the design: nudge says what to look at, method describes the approach in prose with no code, code gives the worked answer. All three are available to students; the tiers exist to make the smallest useful intervention easy to find.

- [ ] **Step 5: Run tests to verify they pass**

Run: `uv run pytest tests/test_student_notebooks.py tests/test_hints.py -v`
Expected: PASS

- [ ] **Step 6: Add both checks to CI**

Extend `tests.yml` to run `scripts/build_student_notebooks.py --check`, failing if generated student notebooks are out of date with their sources.

- [ ] **Step 7: Commit**

```bash
git add scripts/build_student_notebooks.py hints tests/test_student_notebooks.py tests/test_hints.py .github/workflows/tests.yml
git commit -m "feat: solution stripping and hint validation"
```

---

## Deferred to later plans

Named here so their absence is a decision rather than an oversight.

- **Teaching notebooks** for all four stages and the stretch material — plans 2 and 3. This plan ships only `00-smoke.ipynb`, which exists to prove the stack.
- **Widgets** and the site's interactive hint and self-check interface — plan 4. Task 9 and Task 12 build the data those widgets read, so plan 4 adds no new source of truth.
- **Vision imagery** (spec §7.11) — arrives with the stretch notebooks in plan 3. The registry and licence audit already accommodate it: a new entry with licence `CC-BY-SA-4.0` needs no code change, which is the point of building the registry first.
- **Chinese datasets** from SWJTU colleagues — drop in as new registry entries plus one loader each, behind the same interface.

## Manual steps for the teaching team

Not implementable in code, but the foundation is not usable without them.

1. Enable GitHub Pages on the repository, source set to GitHub Actions.
2. Mark the repository as a **template** so each student gets their own copy (spec §7.8).
3. Provision GitHub Copilot seats for both cohorts (spec §9, outstanding item 2).
4. Confirm the Codespaces quota and whether prebuilds are available (spec §9, outstanding item 3).
5. Download the Geofabrik `.pbf` extracts for West Yorkshire and Sichuan into `raw/` before running `scripts/build_osm.py`.

## Done when

- A Codespace opens from this repository, installs in one `postCreate`, and runs `notebooks/01-foundations/00-smoke.ipynb` to completion.
- `uv run pytest` passes; `ruff check` is clean; `scripts/check_licences.py` exits zero.
- `data/` is under 80 MB, every file accounted for by licence and attribution.
- The Quarto site builds and deploys to GitHub Pages, with a data page generated from the registry, a published accessibility statement, and a glossary stub.
- A broken notebook fails CI and publishes nothing.
