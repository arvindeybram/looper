# Changelog

All notable changes to this project are documented here. The format is based on
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and this project adheres
to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-29

First public release, packaged as a Claude Code plugin.

### Added
- `looper` skill: plan (Opus) -> execute (Sonnet) -> validate-until-clean loop,
  with a mandatory permission gate, per-file backups, and an external-gate mode
  (Phase 5b) for slow async validators such as CI or cloud evals.
- `looper-db-guard.py` PreToolUse hook: mechanically blocks database and
  infrastructure writes while a task is armed, scoped to (session, task) with an
  8h approval TTL.
- Plugin manifests (`marketplace.json`, `plugin.json`, `hooks.json`) so install
  is `/plugin marketplace add` + `/plugin install`, with no manual edit of
  `settings.json`.
- `tests/test_guard.py`: executable coverage spec for the guard.
- `SECURITY.md` documenting the threat model, data handled, and fail-open
  behavior.

### Security
- The guard is now **fail-closed** on database clients. Previously it required a
  SQL write keyword to be visible in the command string, so any command that
  delivered SQL via a file, stdin, a pipe, or `--queries-file` bypassed it
  (`mysql < migration.sql`, `cat x.sql | mysql`, `clickhouse-client
  --queries-file`, `sqlite3 ".read"`). These are now blocked.
- Postgres (`psql`) added to the set of guarded database clients.
