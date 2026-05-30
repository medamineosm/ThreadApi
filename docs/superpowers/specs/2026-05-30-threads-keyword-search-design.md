# Threads Keyword Search POC (Python)

## Goal
Build a small Python CLI that calls the Threads Graph API keyword search endpoint, paginates through results, and returns distinct items until the oldest item is earlier than Jan 1 of the current year (UTC).

## Scope
- One-file CLI script using `requests`.
- Hard-coded access token for the POC.
- Prints JSON for unique items to stdout.
- Logs oldest item date per page and stop reason.

Out of scope:
- Persistent storage, retries/backoff, or auth management.
- Service/API wrapper.
- Data transformation beyond deduplication.

## Architecture
- `fetch_threads.py` parses CLI args and drives the fetch loop.
- A single function builds the initial query params and optional `paging.next` URL for subsequent pages.
- Data flow:
  1) Build initial URL and query params.
  2) GET request.
  3) Parse JSON and append unique items (by `id`).
  4) Compute oldest `timestamp` date in the page and log it.
  5) Stop if oldest timestamp is before Jan 1 of current year; otherwise follow `paging.next`.

## CLI Interface
- `--keyword` (required)
- `--since` (optional, default: Jan 1 of current year UTC, as epoch seconds)
- `--until` (optional, default: now UTC, as epoch seconds)
- `--limit` (optional, default: 100)
- `--pretty` (optional, pretty-print JSON)

## API Request
- Endpoint: `https://graph.threads.net/v1.0/keyword_search`
- Query params:
  - `q` = keyword
  - `search_mode` = `KEYWORD`
  - `search_type` = `RECENT`
  - `since`, `until`, `limit`
  - `fields` =
    `id,media_product_type,media_type,media_url,permalink,username,text,timestamp,shortcode,thumbnail_url,children,children.media_url,children.media_type,children.permalink,children.text,is_quote_post,link_attachment_url,gif_url,has_replies,is_reply`
- `access_token` is hard-coded in the script for the POC.

## Pagination and Deduplication
- Use `paging.next` to iterate pages.
- Maintain `seen_ids` set; only append items whose `id` is not in the set.
- For each page, parse all item timestamps and compute the oldest (minimum) timestamp.
- Log: `page=NN oldest_in_page=YYYY-MM-DD` (UTC date).
- Stop conditions:
  1) No `paging.next` present.
  2) Oldest timestamp in page is before Jan 1 of current year UTC. Log stop reason.

## Error Handling
- Non-200 response: print status code and response body; exit with non-zero code.
- JSON parse error: print raw response; exit with non-zero code.
- Missing expected fields: continue best-effort, but log a warning and skip invalid items.

## Output
- Print a JSON array of unique items to stdout.
- If `--pretty` is set, indent with 2 spaces.

## Testing
- Manual: run with the provided access token and keyword to verify pagination and stop condition.
- Check log output for oldest date progression and correct stop reason.

## Risks and Mitigations
- Rate limits or expired token: surface API errors clearly.
- Large result sets: memory use grows with `seen_ids`; acceptable for POC.
