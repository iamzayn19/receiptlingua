# Protocol Versioning

The protocol has its own version, independent of the `receiptlingua` package
versions in `python/`, `javascript/`, and `ruby/`. It is carried in every
response and error envelope as `schema_version`, a semantic version string
(`MAJOR.MINOR.PATCH`).

## Current version

`0.1.0` — pre-1.0, defined for the first time in this milestone.

## Pre-1.0 policy

While the protocol is at `0.x`:

- Breaking changes to the schema (removing/renaming a required field,
  changing a field's type, narrowing an enum) are allowed between minor
  versions, but must:
  - bump the minor version (`0.1.0` -> `0.2.0`),
  - be documented in this file's changelog section below, and
  - update every fixture in `fixtures/` to match.
- Additive, backward-compatible changes (new optional field, new enum
  value that old clients can ignore) bump the patch version.
- `schema_version` itself must never be removed or repurposed — it is the
  one field every client can always rely on to detect a mismatch.

## Post-1.0 policy (once stabilized)

Once the protocol reaches `1.0.0`:

- MAJOR bumps for breaking changes.
- MINOR bumps for backward-compatible additions.
- PATCH bumps for clarifications that don't change validation behavior
  (e.g. description text).
- A MAJOR version bump requires updating all three clients in the same
  release, since they must not silently misinterpret a response built for
  a different major version.

## How clients should use `schema_version`

Clients should read `schema_version` before trusting the rest of the
payload and:

- Accept responses whose MAJOR (or, pre-1.0, MINOR) version matches what
  the client was built against.
- Fail loudly (not silently ignore fields) on a version mismatch, since a
  breaking change may have occurred.

## Changelog

- `0.1.0` — Initial schema: response envelope (image metadata, language/
  script detection, text lines, optional word-level detail, structured
  receipt fields with provenance and status), and the error envelope with
  its initial error code set.
