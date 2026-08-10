# HIMA Reproduction Notes

## Original structure

Multi-advisor council: independent advisors produce suggestions, a leader
aggregates agreement/conflict into a final decision.

## Essential invariants

- Advisors are independent: no advisor sees another advisor's output.
- Leader synthesizes valid advisor outputs into one final queue.
- Fixed advisor count (3) + one leader call.
- Same model for all roles.

## Discarded details

- Race-specific imitation models (`Protoss-a/b/c`, etc.).
- FastAPI local servers and `requests.post("localhost:...")`.
- Hugging Face / transformers model loading.

## SC2-Agent adaptation

- Advisors A/B/C share the same task prompt; only role labels differ.
- Advisors may suggest canonical names, but only Leader finalizes the public queue.
- Malformed advisors are dropped; zero valid advisors → invalid decision.
- Leader malformed → invalid, no repair call.
- CLI mode: `hima`; traces: `hima_traces/`.
