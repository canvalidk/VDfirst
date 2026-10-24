# Trace workbench record v1

Status: implemented prototype; tests define the current protocol. Frame, event
and claim IDs are scoped to record_id.

Scope: a small live VDfirst workbench and portable JSON record. No VD-Newton changes. Existing arithmetic and meaning judgments remain interpreter responses; claims remain unchecked. The initial website uses the three-entry correction dictionary; the Python protocol supports bounded supplied dictionaries.

## Python API

`workbench.py` exports `start_record(dictionary, demand, context='') -> dict`, `validate_record(record) -> dict`, and `apply_command(record, command) -> dict`. All are detached JSON-compatible objects; commands and validation replay from the exact recorded dictionary. Errors are `ValueError`/`RecordError` and leave the caller's object unchanged. `dictionary` is `{name: string, entries: [[headword, definition], ...]}` at start.

Record shape:

```ts
interface TraceRecord {
  format: 'vd-trace-record'; version: 1; record_id: string; sha256: string;
  producer: { name: 'VDfirst'; protocol_version: 1; engine_sha256: string };
  dictionary: { name: string; entries: { index: number; headword: string; definition: string }[]; sha256: string };
  question: { demand: string; context: string };
  commands: Command[];
  events: { id: string; index: number; kind: string; detail: string; change: object | null }[];
  snapshots: Snapshot[];
}
interface Command {
  operation: 'expand' | 'recall' | 'inject' | 'reduce' | 'reopen' | 'clean';
  frame_id: string; position?: number; entry_index?: number;
  response?: string; latents?: string[]; note?: string;
}
interface Snapshot {
  id: string; command_index: number; title: string; root_frame_id: 'F'; event_count: number;
  frames: Frame[]; prediction_set: /* existing VDfirst schema 2 */ object;
}
interface Frame {
  id: string; address: number[]; parent_id: string | null; via_position: number | null;
  render: string; resolved: boolean; reduced: string | null; source_index: number | null;
  headwords: string[]; latents: string[];
  holes: { position: number; headword: string; resolution: 'expand' | 'recall' | 'inject' | null;
    child_frame_id: string | null; source_index: number | null;
    candidates: { entry_index: number; headword: string; definition: string; instantiated_definition: string }[] }[];
}
```

Initial snapshot is S0 with command_index -1. Then one snapshot per successful command. Frame IDs are original-hole paths (`F`, `F/0`, `F/0/1`); committed resolutions are never severed. Events use `event-0`, etc. Claim P<n> refers to event index n. Snapshot titles are generated labels. `source_index` links the containing frame to its dictionary entry. Input children have no dictionary source. Candidates are explicit engine lookups for unresolved holes, never browser tokenization.

Expand/recall require frame, position, entry_index; recall inserts the instantiated entry text literally. Inject requires frame, position, response and analyses its supplied child via the engine. Reduce/reopen target an existing frame; reduce requires response, reopen removes only the overlay and invalidates consumers. Clean accepts a replacement latent-string array, preserving holes. All commands may carry a note. Empty responses and unrelated command fields are rejected. No implicit cleanup, reductions or automatic arithmetic.

Validation checks exact format/version, producer fingerprint, dictionary and record digests, command shape, bounds and exact replay equality of every snapshot/event. The top-level sha256 hashes every other field as sorted-key, compact, non-ASCII-escaped UTF-8 JSON. Dictionary text remains verbatim; engine source hashes normalize CRLF to LF for portable checkouts. Hashes detect accidental edits, not forged authorship. Unsupported versions are rejected for continuation. This is consistency validation, not scientific verification or proof of authorship. Saved snapshots can be displayed offline without replay; the website must label that state accurately. The engine validates again before continuing an imported record.

## Local HTTP bridge

`python workbench_server.py --port 8765` binds 127.0.0.1 only. The bridge is stateless, holds no saved sessions, serves no files and executes no supplied code.

- GET `/api/workbench/health`: `{protocol_version: 1, producer: {...}}`.
- POST `/api/workbench/start`: `{dictionary, demand, context?}` -> `{record}`.
- POST `/api/workbench/command`: `{record, command}` -> `{record}`.
- POST `/api/workbench/validate`: `{record}` -> `{record}`.
- Errors: `{error: string}`, HTTP 400; excessive requests 413.

For development, Vite proxies `/api/workbench` to `http://127.0.0.1:8765`. Website fetches only relative API paths; the production static viewer remains usable for local saved playback without the bridge. No public hosting or cloud storage is added.

## Website milestone

An explicit Workbench section, separate from prepared playback: start force_cart_0; inspect/select frames and open holes; choose candidate definitions; supply responses; reopen reductions; view root results, claims and full saved event history; select past snapshots for read-only playback; continue only at the latest snapshot; download JSON and reopen a local file. Clearly distinguish connected execution, offline saved playback, engine consistency validation and unchecked scientific claims. Import is browser-local until the user explicitly chooses engine validation/continuation.

## Limits and compatibility

Version 1 bounds dictionary entries to 64, commands to 80, frames to 96,
depth to 24, holes per frame to 32 and complete records to 8 MiB. Definitions
and responses are at most 4096 characters; context is at most 8192 and notes
1024. Instantiated text, rendered frames, candidate generation and cumulative
replayed history have additional size budgets. Rejected operations return no
replacement record. The HTTP adapter caps request size, socket duration and
concurrent workers and restricts Host, Origin and content type.

The producer fingerprint describes the loaded engine sources and is frozen
on import. Restart the bridge after source edits. Existing records remain
viewable offline if a newer engine cannot continue them. No migration is
silently attempted. Arbitrary dictionary editing in the website, automatic
checking, the full prediction disjunction, flattening and the whole REPL
command surface remain beyond this small workbench protocol.
