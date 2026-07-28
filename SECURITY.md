# Security

Looper installs one PreToolUse hook (`hooks/looper-db-guard.py`) that intercepts
every `Bash` command in a session where a looper task is armed. Because that hook
sees every shell command you run, here is exactly what it does and does not do.

## No network, no telemetry

The hook makes **zero network calls** and collects **zero telemetry**. It imports
only the Python standard library (`glob`, `json`, `os`, `re`, `sys`, `time`). You
can verify:

```bash
grep -nE 'socket|urllib|http|requests|subprocess|os\.system|popen' plugins/looper/hooks/looper-db-guard.py
# (no matches)
```

It never executes the command it inspects; it only reads it and returns an
allow/deny decision. The pseudo-commands (`looper-guard arm|grant|disarm|status`)
are likewise never executed; they are intercepted and answered by the hook.

## What it reads

On each invocation Claude Code passes the hook a JSON object on **stdin**. The
hook reads three fields and ignores the rest:

| Field | Use |
|-------|-----|
| `tool_name` | Skips everything that is not `Bash`. |
| `tool_input.command` | The command string, matched against the write/read patterns. |
| `session_id` | Scopes approval flags to this session so parallel sessions never interfere. |

The command string is used only for pattern matching and is truncated to 300
characters when echoed back in a deny reason. It is never stored or transmitted.

## What it writes, and where

The only thing the hook writes is small flag files under:

```
~/.claude/looper-approvals/<session_id>__<task-slug>.active     # armed
~/.claude/looper-approvals/<session_id>__<task-slug>.approved   # user granted
```

Each file contains a single Unix timestamp. `.active` marks a task as armed;
`.approved` records that you approved DB/infra writes for it. Files are removed on
`disarm`, and any flag older than 24h is garbage-collected on the next run. This
is an absolute path in your home directory; the hook writes nowhere else.

## Grant scope and expiry

- An approval (`grant`) is scoped to the exact **(session_id, task-slug)** pair.
- It expires **8 hours** after it is recorded (`APPROVAL_TTL`).
- A different session, or a different task in the same session, is **not**
  covered by that grant. It must arm and be granted on its own.
- Stale flags are GC'd after **24 hours** (`STALE_TTL`).

## Fail-open behavior (important, and deliberate)

The hook **fails open**. If it cannot parse its stdin, throws an unhandled
exception, or otherwise exits without emitting an explicit `deny`, Claude Code
proceeds with its normal permission flow, and the command is **not** auto-blocked.

This is a deliberate availability choice: a bug in the guard must not brick your
shell or silently swallow every command. The tradeoff is that during any window
where the hook is crashing, DB/infra writes are **not** guarded. Mitigations:

- The guard logic is small, dependency-free, and covered by
  `tests/test_guard.py` (run it after any change).
- The guard is defense against a loop **accidentally** running an unapproved
  destructive command, not a hardened sandbox. See the boundary below.

## What the guard is, and is not

**It is** a mechanical backstop that makes it hard for the autonomous loop to run
an unapproved write against ClickHouse, MySQL, Postgres, SQLite, or Elasticsearch
content, or to change infrastructure (systemd, crontab), without you approving it
first. It is fail-**closed** on database clients: if a client is invoked and the
SQL is not visibly a pure read (it arrives via file, stdin, a non-literal pipe,
or `--queries-file`/`.read`), it is treated as a write and blocked.

**It is not** a defense against an adversarial or compromised model that is
deliberately trying to evade it. A sufficiently determined executor could encode
a command to dodge the regexes, or run writes from a subagent session the hook
does not see. The looper skill instructs against both (route all DB/infra writes
through the orchestrator's own Bash; never work around a `LOOPER-GUARD BLOCKED`
denial), but those are prompt-level instructions, not mechanical guarantees. Treat
the guard as a seatbelt, not a vault.

## Coverage

Covered write vectors are enumerated as executable test cases in
`plugins/looper/tests/test_guard.py`. If you find a write pattern that the guard
lets through, that is a security bug. Please open an issue with the exact command
(a failing test case is ideal).

## Reporting

Report vulnerabilities by opening a GitHub issue, or privately via the repository
owner's contact on their GitHub profile. Please include a reproducing command.
