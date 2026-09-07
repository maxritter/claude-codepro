# Durable Review State

Use this protocol for every native or companion review launch. The caller owns one record per review role and plan in its resolved run directory. Do not launch a background reviewer when the current mode forbids recording its handle; defer the launch until writes are permitted.

## Resolve and persist identity

Resolve `SESSION_ID` from the current runtime's confirmed session identity and `LANE_ID` from the invocation's parsed `--lane`, empty for a non-lane run. Use `~/.pilot/sessions/<session>/lanes/<lane>/` for a lane and `~/.pilot/sessions/<session>/` otherwise. Require session id, role, and slug to match `^[A-Za-z0-9][A-Za-z0-9_-]*$`; a nonempty lane must match Pilot's `^[a-z0-9][a-z0-9-]{0,63}$` contract. Reject `.` and `..`, separators, and other values rather than sanitizing distinct identities into the same path. Never infer a lane from a branch or another record. Missing session identity is a blocker to an asynchronous launch, not permission to use a shared `default` record.

Set `REVIEW_STATE_FILE` to `<run-dir>/review-<provider>-<role>-<slug>.json`, with provider exactly `native` or `companion`, so parallel reviewers of the same role never overwrite one another. Before launching, read any existing record and verify its session, lane, plan path, provider, and role. Recover its original handle first; never overwrite a live review or treat a missing in-memory variable as permission to launch again. An interrupted `launching` record without a handle requires reconciling the runtime's task inventory or broker launch output; do not guess that no job exists.

Before reusing completed or collected evidence, compare `reviewed_sha256` with the current review anchor. For a changes review, that anchor includes the supplied diff snapshot, resolved base/revision, and file scope alongside the plan; unchanged plan prose alone cannot establish freshness. Retain those scope/revision inputs in the record so the fingerprint can be reproduced. A mismatch makes the evidence stale and requires a fresh review, but only after the original live job is terminal; never overwrite or relaunch live work.

Atomically record `launching` before the launch, then the returned handle immediately, before independent work or a phase handoff. The JSON record contains `session_id`, `lane_id`, `plan_path`, `slug`, `role`, `provider` (`native` or `companion`), `native_agent_id` or `job_id`, `prompt_path` (null for an inline native prompt), `reviewed_sha256`, `state`, `retry_count`, and `result_path` (null until a validated result is saved). Hash the exact reviewed draft before launching. Keep prior terminal handles in `attempts` when retrying.

For each update, render the complete JSON into `REVIEW_RECORD_JSON` using structured serialization, then atomically replace the record on the same filesystem:

```bash
REVIEW_STATE_FILE="<resolved-run-dir>/review-<provider>-<role>-<slug>.json" \
REVIEW_RECORD_JSON='<serialized record>' python3 - <<'PY'
import json
import os
import tempfile
from pathlib import Path

target = Path(os.environ["REVIEW_STATE_FILE"])
record = json.loads(os.environ["REVIEW_RECORD_JSON"])
target.parent.mkdir(parents=True, exist_ok=True)
fd, temporary = tempfile.mkstemp(prefix=target.name + ".", dir=target.parent)
try:
    with os.fdopen(fd, "w") as stream:
        json.dump(record, stream)
        stream.write("\n")
        stream.flush()
        os.fsync(stream.fileno())
    os.replace(temporary, target)
finally:
    if os.path.exists(temporary):
        os.unlink(temporary)
PY
```

Use structured tool/file inputs instead of shell interpolation when values contain quotes. A failed persistence write must be recovered before independent work; keep the returned live handle and never relaunch merely because saving it failed.

## Observe and recover

After compaction and at collection, reload this record, verify identity, and use its original live handle with the current runtime's actual status/wait tool. For native tools, bound each wait to at most 30 seconds when their schema permits; otherwise use their documented yielding mechanism. Resume independent work or give a progress update between observations. A wait timeout is an observation boundary, not a total job deadline or cancellation authority.

Only a completed final response with valid provider schema is review evidence. Native reviewer JSON must have matching `plan_file`. The companion schema (`verdict`, `summary`, `findings`, `next_steps`) has no `plan_file`: bind it through the confirmed broker job id and this record's prompt path, reviewed content hash, and plan/lane identity. Record `completed` after terminal confirmation and `collected` only after validating and consuming that result. Persist transient observation errors without replacing the handle. Retry only after confirmed terminal failure/cancellation or confirmed missing runtime handle, with the caller's existing retry policy. Preserve the original attempt in the record. A user stop cancels owned work using exposed controls and confirms its terminal state before replacement.

Retain the record through the workflow so compaction can distinguish collected, incomplete, and live reviews. Prompt/result cleanup is permitted only after terminal collection; never remove the only recoverable handle while work is live. Do not claim a saved JSON file by itself proves the native reviewer completed.
