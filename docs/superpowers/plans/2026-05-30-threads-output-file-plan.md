# Threads Output File Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Write the fetched results to a timestamped JSON file while keeping progress logs on stdout.

**Architecture:** Generate a launch-time filename and write the final JSON array to that path after fetching completes. CLI adds an optional `--output-dir` to choose the folder.

**Tech Stack:** Python 3, `pytest`

---

## File Structure

- Modify: `fetch_threads.py` — add output path generation and file write.
- Modify: `tests/test_fetch_threads.py` — add tests for filename/path selection and saved log.

---

### Task 1: Add failing tests for output file behavior

**Files:**
- Modify: `tests/test_fetch_threads.py`

- [ ] **Step 1: Write failing tests**

```python
def test_output_path_uses_timestamp_and_dir(tmp_path):
    ts = datetime(2026, 5, 30, 21, 30, 45, tzinfo=timezone.utc)
    out_path = fetch_threads.build_output_path(output_dir=str(tmp_path), now=ts)
    assert out_path.name == "threads_20260530_213045.json"
    assert out_path.parent == tmp_path


def test_write_results_logs_saved_to(tmp_path):
    logs = []

    def log_fn(msg):
        logs.append(msg)

    ts = datetime(2026, 5, 30, 21, 30, 45, tzinfo=timezone.utc)
    out_path = tmp_path / "threads_20260530_213045.json"
    fetch_threads.write_results_file(out_path, [{"id": "1"}], pretty=False, log_fn=log_fn)
    assert out_path.exists()
    assert any(msg.startswith("saved_to=") for msg in logs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch_threads.py::test_output_path_uses_timestamp_and_dir -v`
Expected: FAIL with `AttributeError` or missing function.

- [ ] **Step 3: Run tests to verify saved_to log fails**

Run: `pytest tests/test_fetch_threads.py::test_write_results_logs_saved_to -v`
Expected: FAIL with missing function.

---

### Task 2: Implement output file writing

**Files:**
- Modify: `fetch_threads.py`

- [ ] **Step 1: Add helpers for output path and writing**

```python
from pathlib import Path


def build_output_path(output_dir: str, now: datetime) -> Path:
    dirname = Path(output_dir or ".")
    filename = f"threads_{now.strftime('%Y%m%d_%H%M%S')}.json"
    return dirname / filename


def write_results_file(path: Path, results: List[Dict], pretty: bool, log_fn: Callable[[str], None]) -> None:
    text = json.dumps(results, indent=2) if pretty else json.dumps(results)
    path.write_text(text)
    log_fn(f"saved_to={path}")
```

- [ ] **Step 2: Add CLI args and wire into main**

```python
    parser.add_argument("--output-dir", default=None)

    output_path = build_output_path(args.output_dir, now)
    if args.output_dir and not output_path.parent.exists():
        raise RuntimeError(f"output_dir_not_found={output_path.parent}")
    write_results_file(output_path, results, args.pretty, print)
```

- [ ] **Step 3: Run tests to verify they pass**

Run: `pytest tests/test_fetch_threads.py -v`
Expected: PASS

---

## Self-Review Checklist

- Spec coverage: timestamped filename, optional output-dir, saved_to log, error when dir missing.
- No placeholders: all steps include concrete code and commands.
- Type consistency: helper names match tests and implementation.
