# Threads Rate Limit Optimization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add request pacing and 429 backoff to the Threads keyword search CLI to be rate-limit friendly while staying fast.

**Architecture:** Add a small token-bucket style limiter and optional 429 backoff in `fetch_threads.py`, exposed via new CLI flags. Tests use a fake time source to assert sleep behavior and backoff without real delays.

**Tech Stack:** Python 3, `pytest`

---

## File Structure

- Modify: `fetch_threads.py` — add rate limiter, new CLI args, 429 backoff.
- Modify: `tests/test_fetch_threads.py` — add tests for limiter pacing and 429 backoff.

---

### Task 1: Add failing tests for pacing and 429 backoff

**Files:**
- Modify: `tests/test_fetch_threads.py`

- [ ] **Step 1: Write failing tests**

```python
def test_rate_limiter_sleeps_when_over_rps(monkeypatch):
    times = [0.0, 0.0, 0.4]
    slept = []

    def fake_time():
        return times.pop(0)

    def fake_sleep(seconds):
        slept.append(seconds)

    page = {"data": [], "paging": {"next": None}}

    def fake_get(url, params=None):
        class Resp:
            status_code = 200

            def json(self_inner):
                return page

            text = json_module.dumps(page)

        return Resp()

    results = fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=0,
        until=int(datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()),
        limit=1,
        access_token="token",
        cutoff_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        request_get=fake_get,
        log_fn=lambda *_: None,
        max_rps=2.0,
        burst=1,
        time_fn=fake_time,
        sleep_fn=fake_sleep,
    )

    assert results == []
    assert slept
    assert slept[0] > 0


def test_backoff_on_429(monkeypatch):
    slept = []

    def fake_sleep(seconds):
        slept.append(seconds)

    responses = [429, 200]
    page = {"data": [], "paging": {"next": None}}

    def fake_get(url, params=None):
        status = responses.pop(0)

        class Resp:
            status_code = status

            def json(self_inner):
                return page

            text = json_module.dumps(page)

        return Resp()

    fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=0,
        until=int(datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()),
        limit=1,
        access_token="token",
        cutoff_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        request_get=fake_get,
        log_fn=lambda *_: None,
        max_rps=10.0,
        burst=1,
        time_fn=lambda: 0.0,
        sleep_fn=fake_sleep,
    )

    assert 2.0 in slept
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_fetch_threads.py::test_rate_limiter_sleeps_when_over_rps -v`
Expected: FAIL with unexpected keyword arguments or missing behavior.

- [ ] **Step 3: Run tests to verify backoff test fails**

Run: `pytest tests/test_fetch_threads.py::test_backoff_on_429 -v`
Expected: FAIL with unexpected keyword arguments or missing behavior.

---

### Task 2: Implement pacing and backoff

**Files:**
- Modify: `fetch_threads.py`

- [ ] **Step 1: Add minimal rate limiter and backoff support**

```python
def collect_keyword_search(
    keyword: str,
    since: int,
    until: int,
    limit: int,
    access_token: str,
    cutoff_date: datetime,
    request_get: Callable = requests.get,
    log_fn: Callable[[str], None] = print,
    max_rps: float = 2.0,
    burst: int = 1,
    time_fn: Callable[[], float] = None,
    sleep_fn: Callable[[float], None] = None,
) -> List[Dict]:
    time_fn = time_fn or (lambda: datetime.now(timezone.utc).timestamp())
    sleep_fn = sleep_fn or (lambda s: __import__("time").sleep(s))

    tokens = float(burst)
    last_time = time_fn()
    interval = 1.0 / max_rps if max_rps > 0 else 0.0

    def pace():
        nonlocal tokens, last_time
        now = time_fn()
        elapsed = max(0.0, now - last_time)
        if interval > 0:
            tokens = min(float(burst), tokens + (elapsed / interval))
        last_time = now
        if tokens >= 1.0:
            tokens -= 1.0
            return
        if interval > 0:
            sleep_for = (1.0 - tokens) * interval
            log_fn(f"sleep_ms={int(sleep_for * 1000)}")
            sleep_fn(sleep_for)
            tokens = 0.0

    # inside while loop, before request:
    pace()
    resp = request_get(...)
    if resp.status_code == 429:
        log_fn("rate_limit_hit")
        sleep_fn(2.0)
        continue
```

- [ ] **Step 2: Add CLI args**

```python
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--keyword", required=True)
    parser.add_argument("--since", type=int, default=None)
    parser.add_argument("--until", type=int, default=None)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--pretty", action="store_true")
    parser.add_argument("--max-rps", type=float, default=2.0)
    parser.add_argument("--burst", type=int, default=1)
    return parser.parse_args()
```

- [ ] **Step 3: Wire args into main**

```python
    results = collect_keyword_search(
        keyword=args.keyword,
        since=since,
        until=until,
        limit=args.limit,
        access_token=access_token,
        cutoff_date=cutoff,
        max_rps=args.max_rps,
        burst=args.burst,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_fetch_threads.py -v`
Expected: PASS

---

## Self-Review Checklist

- Spec coverage: pacing, 429 backoff, CLI args, logging.
- No placeholders: all steps include concrete code and commands.
- Type consistency: new parameters used consistently in tests and implementation.
