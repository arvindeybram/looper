# Draft: submission to the official Claude Code plugin directory

Target: `anthropics/claude-plugins-official` (submit via the plugin directory
submission form linked from that repo's README). Do this AFTER the guard tests
are green and the repo is public, because they have quality and security bars.

## Pre-submission checklist

- [ ] Repo public at `github.com/arvindeybram/looper`
- [ ] `python3 plugins/looper/tests/test_guard.py` passes
- [ ] `/plugin marketplace add arvindeybram/looper` + install works from a clean machine
- [ ] `README.md` has the demo GIF rendered (not a broken link)
- [ ] `SECURITY.md` present
- [ ] `v0.1.0` tagged and a GitHub Release published
- [ ] LICENSE present (MIT)

## Suggested field values

**Name:** looper

**Short description (one line):**
Autonomous plan-execute-validate loop with per-file backups and a fail-closed
database/infrastructure permission gate.

**Category:** development / automation

**Longer description:**
Looper runs a task as a plan (Opus) -> execute (Sonnet) -> validate-until-clean
loop. The plan must include a runnable validation contract and a Touch list of
everything it will read or write; a fresh validator runs every check each round
rather than letting the executor grade its own work. Before any file is changed
it is backed up, and a mechanical PreToolUse hook blocks writes to ClickHouse,
MySQL, Postgres, SQLite, and Elasticsearch content (and to infrastructure) until
the user explicitly approves them, scoped to the session and task. Includes an
external-gate mode for slow async validators such as CI or cloud evals.

**Keywords:** automation, agentic-workflows, validation, guardrails, safety

**Security note for reviewers:** The plugin ships one PreToolUse(Bash) hook. It
makes no network calls and no telemetry, uses only the Python standard library,
reads three fields from the hook stdin, and writes only timestamp flag files
under `~/.claude/looper-approvals/`. Full model in SECURITY.md. Guard coverage is
an executable test suite (`tests/test_guard.py`).

## Note
Anthropic's directory tells users to trust a plugin before installing because
Anthropic cannot verify contents. Lead the submission with the SECURITY.md link
and the test suite; that is the differentiator for this plugin.
