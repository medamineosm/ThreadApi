# Threads Keyword Search Output File (Python)

## Goal
Write the collected JSON results to a single file with a timestamped name while keeping progress logs on stdout.

## Scope
- Generate a timestamped filename at script launch.
- Save the full JSON array to that file.
- Keep existing console logs (page, oldest date, sleep, rate limit).

Out of scope:
- Streaming partial JSON while fetching.
- Appending across runs.

## Output Behavior
- Default filename: `threads_YYYYMMDD_HHMMSS.json` in the current working directory.
- If `--output-dir` is provided, place the file there using the same filename pattern.
- Log a final line: `saved_to=<path>` after writing the file.

## CLI Changes
- Add `--output-dir` (optional).

## Error Handling
- If the output directory does not exist, raise a clear error and exit non-zero.
- If writing fails, surface the exception message.

## Testing
- Unit test for filename generation and output path selection.
- Unit test to ensure `saved_to` log is emitted.
