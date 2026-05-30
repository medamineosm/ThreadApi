# Threads Raw Output File (Python)

## Goal
Save the raw API payloads for each page into a single timestamped JSON file, while keeping progress logs on stdout.

## Scope
- Collect raw page payloads during pagination.
- Write one JSON file containing metadata and all raw pages.
- Keep existing logs unchanged.

Out of scope:
- Streaming to disk during fetch.
- NDJSON output.

## Output Format
Single JSON file:

```json
{
  "collected_at": "2026-05-30T21:30:45Z",
  "pages": [
    {"data": [...], "paging": {...}},
    {"data": [...], "paging": {...}}
  ]
}
```

## Implementation Notes
- Append each raw `payload` before filtering.
- Write the raw structure to the timestamped output file.
- Optionally keep filtered results to stdout only.

## Testing
- Unit test ensures raw pages are captured and written.
