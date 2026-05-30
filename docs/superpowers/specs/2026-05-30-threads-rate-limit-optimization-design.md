# Threads Keyword Search Rate Limit Optimization (Python)

## Goal
Add rate-limit friendly request pacing to the existing keyword search CLI to improve throughput while staying under API limits.

## Scope
- Add a token-bucket style pacing mechanism in the request loop.
- Expose `--max-rps` and `--burst` CLI flags.
- Log sleep time when pacing is applied.
- Add a simple 429 backoff behavior.

Out of scope:
- Parallel requests.
- Automatic limit discovery.
- Persistent caching.

## Architecture
- Keep a lightweight rate limiter in `fetch_threads.py`.
- The limiter tracks the next allowed time for a request and sleeps when needed.
- Apply pacing before each API request in `collect_keyword_search`.

## CLI Interface Changes
- `--max-rps` (float, default 2.0): maximum requests per second.
- `--burst` (int, default 1): allow brief bursts up to N requests without delay.

## Pacing Behavior
- Compute minimum interval as `1 / max_rps`.
- Maintain a small token bucket with `burst` capacity.
- Before each request, consume a token; if empty, sleep until a token refills.
- Log `sleep_ms=<ms>` only when a sleep occurs.

## Error Handling
- If API returns 429, log `rate_limit_hit` and sleep for 2 seconds, then continue respecting the limiter.
- Non-200s still raise an error as before.

## Logging
- Continue `page` and `oldest_in_page` logs.
- Add `sleep_ms` when pacing is applied.
- Add `rate_limit_hit` on 429 responses.

## Testing
- Unit test for rate limiter sleep behavior using a fake time source.
- Unit test for 429 backoff path.
