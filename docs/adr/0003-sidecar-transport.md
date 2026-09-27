# ADR 0003: Sidecar transport -- newline-delimited JSON over stdio

Date: 2026-09-27

## Context

`protocol/README.md` deliberately left the sidecar transport undecided
when the JSON protocol schema was defined: "stdio (newline-delimited JSON
over the sidecar's stdin/stdout) vs. a local Unix domain socket (or named
pipe on Windows)." At the time there was no real sidecar process yet to
build the decision around -- `PaddleOCREngine` (see ADR 0002) used a
one-process-per-call subprocess stopgap that never needed a transport
decision at all, since each call was a single request/response over a
throwaway process's stdin/stdout.

That stopgap paid PaddleOCR's full interpreter-startup + model-load cost
on every single `recognize()` call, which defeats any benefit of having a
sidecar at all once more than one image needs to be scanned. Replacing it
with a real persistent daemon (loads the model once, serves many
requests) requires actually picking a transport, since "one request, one
throwaway process" no longer applies.

## Options considered

**Newline-delimited JSON over stdin/stdout (chosen)**

- The parent process owns the child's stdin/stdout file descriptors
  directly via `subprocess.Popen` -- no separate listening socket to
  create, bind, or clean up, and no port (or named-pipe path) to pick,
  collide on, or leak if the parent crashes.
- Framing is trivial: one JSON object per line, `\n`-terminated. JSON
  values never contain a literal unescaped newline, so a line is always
  exactly one message; no length-prefixing needed.
- Process lifecycle is the *only* lifecycle to manage: if the child dies,
  its stdout simply hits EOF (read returns empty) and/or its stdin write
  raises `BrokenPipeError` -- both trivially detectable without any extra
  liveness protocol. A socket-based daemon needs its own liveness/cleanup
  story (stale socket files, orphaned listeners) on top of process
  lifecycle.
- Identical behavior on macOS and Linux (this project's actual target
  platforms -- see ADR 0002's environment notes); no platform-specific
  branching for socket type (Unix domain socket vs. Windows named pipe)
  is needed at all.
- No new dependency: `subprocess` + `json`, both already used by the
  one-shot stopgap this replaces.

**Local Unix domain socket (rejected for now)**

- Would allow multiple independent client processes to attach to one
  long-lived daemon (e.g. several CLI invocations sharing one warm
  PaddleOCR daemon), which stdio cannot do -- stdio is inherently
  one-parent-one-child.
- But: needs a socket path (where? per-user tmp dir, with permissions and
  collision handling), needs cleanup of the socket file on daemon exit
  (including *unclean* exit -- crash, SIGKILL), and needs a decision on
  Windows (named pipes are a different API, not a Unix domain socket at
  all) that this project doesn't currently need to make, since nothing
  today asks for multi-client sharing.
- The actual, current need -- one Python process (a `ReceiptOCR`/
  `PaddleOCREngine` instance) driving its own sidecar across multiple
  `recognize()` calls -- is exactly the shape stdio already fits with
  zero extra lifecycle surface. Building the socket-sharing machinery now
  would be speculative: nothing in this codebase yet has multiple
  independent processes that need to share one daemon.

## Decision

**Newline-delimited JSON over the sidecar's stdin/stdout.** One JSON
object per line in each direction; the parent (`PaddleOCREngine`) owns
the child's pipes via `subprocess.Popen` and correlates requests to
responses with a small integer `id` field, even though the current v1
daemon is single-request-at-a-time FIFO (see
`_paddle_sidecar_daemon.py`'s docstring) and doesn't strictly need
correlation yet -- it's included so a future concurrent/pipelined daemon
doesn't need a wire-format change, only a scheduling change.

Shutdown is a `{"cmd": "shutdown"}` message (preferred, lets the daemon
exit its read loop and return 0 cleanly) with SIGTERM/closed-stdin as a
fallback the parent uses if the daemon doesn't exit promptly. See
`PaddleOCREngine.close()` for the actual sequence.

This closes the open item flagged in `protocol/README.md`'s "Open
questions" section and referenced from `ARCHITECTURE.md`; both are
updated to point here instead of calling the transport undecided.

## Consequences / follow-up

- If a future need arises for multiple independent processes to share one
  warm daemon (e.g. a batch CLI tool and a long-running server both using
  the same PaddleOCR sidecar), that's a Unix-domain-socket-shaped problem
  this ADR deliberately doesn't solve -- revisit then, informed by an
  actual concrete requirement rather than speculatively now.
- The v1 daemon is single-request-at-a-time (documented in
  `_paddle_sidecar_daemon.py`); the `id` field in the wire format leaves
  room to make it concurrent later without another transport ADR.
- This decision is scoped to the PaddleOCR sidecar specifically. It's a
  reasonable default for any future Python-backed sidecar this project
  adds, but each one should still confirm stdio fits its actual usage
  pattern rather than assuming this ADR speaks for all of them forever.
