import json as json_module
from datetime import datetime, timezone

import fetch_threads


def make_item(item_id, ts):
    return {
        "id": item_id,
        "timestamp": ts,
    }


def test_dedup_and_pagination_stop_at_cutoff(monkeypatch):
    cutoff = datetime(2026, 1, 1, tzinfo=timezone.utc)
    page1 = {
        "data": [
            make_item("1", "2026-02-01T00:00:00+0000"),
            make_item("2", "2026-01-15T00:00:00+0000"),
        ],
        "paging": {"next": "https://example.com/page2"},
    }
    page2 = {
        "data": [
            make_item("2", "2026-01-15T00:00:00+0000"),
            make_item("3", "2025-12-31T23:59:59+0000"),
        ],
        "paging": {"next": "https://example.com/page3"},
    }

    responses = [page1, page2]
    calls = []

    def fake_get(url, params=None):
        calls.append(url)
        data = responses.pop(0)

        class Resp:
            status_code = 200

            def json(self_inner):
                return data

            text = json_module.dumps(data)

        return Resp()

    since_dt = datetime(2025, 1, 1, tzinfo=timezone.utc)
    until_dt = datetime(2026, 12, 31, tzinfo=timezone.utc)

    results, _ = fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=int(since_dt.timestamp()),
        until=int(until_dt.timestamp()),
        limit=100,
        access_token="token",
        cutoff_date=cutoff,
        request_get=fake_get,
        log_fn=lambda *_: None,
    )

    ids = sorted([item["id"] for item in results])
    assert ids == ["1", "2", "3"]
    assert calls == [fetch_threads.BASE_URL, "https://example.com/page2"]


def test_parse_timestamp_accepts_z_suffix():
    dt = fetch_threads.parse_timestamp("2026-02-01T00:00:00Z")
    assert dt.tzinfo is not None


def test_filters_items_outside_since_until_window():
    since_dt = datetime(2026, 5, 7, 19, 0, 0, tzinfo=timezone.utc)
    until_dt = datetime(2026, 5, 7, 19, 8, 56, tzinfo=timezone.utc)
    page = {
        "data": [
            make_item("1", "2026-05-07T18:59:59+0000"),
            make_item("2", "2026-05-07T19:05:00+0000"),
            make_item("3", "2026-05-07T19:10:09+0000"),
        ]
    }

    def fake_get(url, params=None):
        class Resp:
            status_code = 200

            def json(self_inner):
                return page

            text = json_module.dumps(page)

        return Resp()

    results, _ = fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=int(since_dt.timestamp()),
        until=int(until_dt.timestamp()),
        limit=100,
        access_token="token",
        cutoff_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        request_get=fake_get,
        log_fn=lambda *_: None,
    )

    assert [item["id"] for item in results] == ["2"]


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

    results, _ = fetch_threads.collect_keyword_search(
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


def test_stops_on_repeat_cursor(monkeypatch):
    logs = []

    def log_fn(msg):
        logs.append(msg)

    calls = []
    payload1 = {
        "data": [make_item("1", "2026-05-07T00:00:00+0000")],
        "paging": {"next": "NEXT"},
    }
    payload2 = {
        "data": [make_item("2", "2026-05-07T00:00:01+0000")],
        "paging": {"next": "NEXT"},
    }
    responses = [payload1, payload2]

    def fake_get(url, params=None):
        calls.append(url)
        data = responses.pop(0)

        class Resp:
            status_code = 200

            def json(self_inner):
                return data

            text = json_module.dumps(data)

        return Resp()

    results, _ = fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=0,
        until=int(datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()),
        limit=10,
        access_token="token",
        cutoff_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        request_get=fake_get,
        log_fn=log_fn,
        max_pages=100,
    )

    assert len(calls) == 2
    assert any("repeat_cursor" in msg for msg in logs)
    assert {item["id"] for item in results} == {"1", "2"}


def test_stops_on_max_pages(monkeypatch):
    logs = []

    def log_fn(msg):
        logs.append(msg)

    payload = {
        "data": [make_item("1", "2026-05-07T00:00:00+0000")],
        "paging": {"next": "NEXT1"},
    }
    payload2 = {
        "data": [make_item("2", "2026-05-07T00:00:01+0000")],
        "paging": {"next": "NEXT2"},
    }

    responses = [payload, payload2]
    calls = []

    def fake_get(url, params=None):
        calls.append(url)
        data = responses.pop(0)

        class Resp:
            status_code = 200

            def json(self_inner):
                return data

            text = json_module.dumps(data)

        return Resp()

    results, _ = fetch_threads.collect_keyword_search(
        keyword="rolex",
        since=0,
        until=int(datetime(2027, 1, 1, tzinfo=timezone.utc).timestamp()),
        limit=10,
        access_token="token",
        cutoff_date=datetime(2025, 1, 1, tzinfo=timezone.utc),
        request_get=fake_get,
        log_fn=log_fn,
        max_pages=1,
    )

    assert len(calls) == 1
    assert any("stop=max_pages" in msg for msg in logs)
    assert {item["id"] for item in results} == {"1"}
