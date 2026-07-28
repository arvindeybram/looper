# Looper

**Claude Code says it's done. It isn't.** The tests it "ran" were the two it
remembered writing, it quietly edited a config it shouldn't have touched, and you
find out forty minutes later.

Looper is a plan-execute-validate loop that closes that gap. A planning pass
writes an explicit validation contract before any code is touched, a fresh
validator actually runs every check each round (it never grades its own work),
and a mechanical guard blocks database and infrastructure writes until you
approve them. It also backs up every file before it changes it.

![Looper demo](docs/looper-demo.gif)

## Why it exists

Autonomous coding loops fail in three predictable ways:

- **False done.** The agent declares success against checks it invented, not the
  ones that prove the task.
- **Silent blast radius.** A run meant to touch one file restarts a service,
  truncates a table, or rewrites a config, and nothing stops it.
- **No undo.** Files are edited in place with no snapshot to roll back to.

Looper answers each mechanically, not with a prompt that says "please be careful":

| Failure | Looper's answer |
|---------|-----------------|
| False done | The plan must contain a runnable **Validation section**; a **fresh** validator runs it every round and returns evidence, not a claim. |
| Silent blast radius | A PreToolUse hook **fail-closes** on DB/infra writes and pauses for your explicit approval, scoped to this session and task. |
| No undo | Every existing file is copied to `.looper-backups/<timestamp>/` before the first edit. |

## How it works

1. **Plan (Opus).** Produces a step plan with a Validation section, an edge-case
   review, and a Touch list tagging every file/table/service as `read-only` or
   `modifies`. A second Opus pass critiques it.
2. **Permission gate.** If the Touch list includes any write to ClickHouse,
   MySQL, Postgres, SQLite, or Elasticsearch content, or any infrastructure
   change, Looper stops and asks you exactly what will be modified. Nothing
   destructive happens without a fresh approval.
3. **Backup.** Every file is snapshotted before its first edit.
4. **Execute (Sonnet).** Implements the approved plan.
5. **Validate until clean (Sonnet).** A fresh validator runs every check each
   iteration; failures go to a fixer; then it fully re-validates. Up to 10 fix
   cycles, then it stops and reports honestly rather than claiming success.

There is also an external-gate mode (Phase 5b) for loops whose validator is a
slow async system such as CI or a cloud eval, which self-paces re-checks and
tells genuine failures apart from transient infrastructure ones.

## The guard

The permission gate is enforced by a mechanical PreToolUse hook, not by asking
the model nicely. It is **fail-closed** on database clients: if a client
(`clickhouse-client`, `mysql`, `psql`, `sqlite3`) is invoked and the SQL is not
visibly a pure read, it is blocked, including the cases a naive keyword filter
misses:

```
mysql mydb < migration.sql            # blocked (SQL hidden in a file)
cat migration.sql | mysql mydb        # blocked (piped in)
clickhouse-client --queries-file x.sql# blocked (file flag)
sqlite3 app.db ".read migration.sql"  # blocked (dot-read)

mysql -e "SELECT * FROM users"        # allowed (visible read)
echo "SELECT 1" | clickhouse-client   # allowed (visible read)
```

Read the full threat model, including the deliberate fail-open-on-crash behavior
and what the guard is **not**, in [SECURITY.md](SECURITY.md).

## Install

**Plugin (recommended):**

```
/plugin marketplace add arvindeybram/looper
/plugin install looper@looper
```

<details>
<summary>Manual install (no plugin system)</summary>

```bash
# Skill
mkdir -p ~/.claude/skills/looper
cp plugins/looper/skills/looper/SKILL.md ~/.claude/skills/looper/

# Guard hook
cp plugins/looper/hooks/looper-db-guard.py ~/.claude/hooks/
chmod +x ~/.claude/hooks/looper-db-guard.py
```

Then add this to the `hooks` block of `~/.claude/settings.json`:

```json
{
  "hooks": {
    "PreToolUse": [
      {
        "matcher": "Bash",
        "hooks": [
          { "type": "command",
            "command": "\"$HOME\"/.claude/hooks/looper-db-guard.py",
            "timeout": 10 }
        ]
      }
    ]
  }
}
```

Skipping the hook step gives you the loop **without** the guard, so prefer the
plugin install.
</details>

## Usage

```
/looper Fix the flaky retry in worker.py, add a backoff, and cover it with tests.
```

Looper arms the guard, plans, asks permission if the plan touches a database or
infrastructure, executes, then validates until clean and disarms.

## Tests

The guard's coverage is an executable spec:

```bash
python3 plugins/looper/tests/test_guard.py
```

It asserts the full block/allow matrix, the arm-block-grant-pass-disarm flow, and
parallel-session isolation. If you find a write that slips through, that is a
security bug: a failing test case is the ideal report.

## License

MIT. See [LICENSE](LICENSE).
