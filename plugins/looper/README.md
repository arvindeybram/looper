# looper (plugin)

Autonomous plan-execute-validate loop for Claude Code, with per-file backups and
a fail-closed database/infrastructure permission gate.

- Skill: `skills/looper/SKILL.md`
- Guard hook: `hooks/looper-db-guard.py` (registered via `hooks/hooks.json`)
- Tests: `tests/test_guard.py`

Full documentation, install instructions, and the security model are in the
repository root: [README](../../README.md) and [SECURITY.md](../../SECURITY.md).

```
/plugin marketplace add arvindeybram/looper
/plugin install looper@looper
/looper <your task>
```
