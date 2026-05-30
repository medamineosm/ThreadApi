# Threads Raw Output Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Save raw API payloads for each page into a single timestamped JSON file while keeping existing logs and filtered processing.

**Architecture:** Capture each page payload in-memory as it is fetched, then write a single JSON file with `collected_at` and `pages` after the loop finishes. Keep filtered output to stdout only.

**Tech Stack:** Python 3, `pytest`

---

## File Structure

- Modify: `fetch_threads.py` — collect raw payloads and write raw output.
- Modify: `tests/test_fetch_threads.py` — tests for raw output structure.

---

### Task 1: Add failing tests for raw output

**Files:**
- Modify: `tests/test_fetch_threads.py`

- [ ] **Step 1: Write failing tests**

```python
def test_write_raw_results_file_structure(tmp_path):
    logs = []

    def log_fn(msg):
        logs.append(msg)

    ts = datetime(2026, 5, 30, 21, 30, 45, tzinfo=timezone.utc)
    out_path = tmp_path / "threads_20260530_213045.json"
    raw_pages = [{"data": [{"id": "1"}], "paging": {"next": None}}]

    fetch_threads.write_raw_results_file(out_path, raw_pages, ts, pretty=False, log_fn=log_fn)

    content = out_path.read_text()
    payload = json_module.loads(content)
    assert payload["collected_at"] == "2026-05-30T21:30:45Z"
    assert payload["pages"] == raw_pages
    assert any(msg.startswith("saved_to=") for msg in logs)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch_threads.py::test_write_raw_results_file_structure -v`
Expected: FAIL with missing function.

---

### Task 2: Implement raw output collection and writing

**Files:**
- Modify: `fetch_threads.py`

- [ ] **Step 1: Add raw output writer**

```python
def write_raw_results_file(
    path: Path,
    raw_pages: List[Dict],
    collected_at: datetime,
    pretty: bool,
    log_fn: Callable[[str], None],
) -> None:
    payload = {
        "collected_at": collected_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "pages": raw_pages,
    }
    text = json.dumps(payload, indent=2) if pretty else json.dumps(payload)
    path.write_text(text)
    log_fn(f"saved_to={path}")
```

- [ ] **Step 2: Capture raw pages in collect_keyword_search**

```python
    raw_pages: List[Dict] = []
    ...
        payload = resp.json()
        raw_pages.append(payload)
        data = payload.get("data", [])
    ...
    return results, raw_pages
```

- [ ] **Step 3: Wire raw output into main**

```python
    results, raw_pages = collect_keyword_search(...)
    write_raw_results_file(output_path, raw_pages, now, args.pretty, print)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetch_threads.py -v`
Expected: PASS

---

## Self-Review Checklist

- Spec coverage: raw pages captured, output structure includes collected_at and pages.
- No placeholders: all steps include concrete code and commands.
- Type consistency: tuple return used consistently by tests and main.
