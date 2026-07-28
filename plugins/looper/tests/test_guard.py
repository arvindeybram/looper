#!/usr/bin/env python3
"""Regression tests for looper-db-guard.py.

Runs the hook as a black box: feeds it PreToolUse JSON on stdin and asserts on
the deny/allow decision. Covers the fail-closed matrix (the file/stdin/pipe
hole that motivated the rewrite), the arm->block->grant->pass->disarm flow,
and (session_id, slug) isolation between parallel sessions.

Usage:  python3 tests/test_guard.py        # exits non-zero on any failure
"""
import json
import os
import subprocess
import sys
import tempfile
import time

HOOK = os.path.join(os.path.dirname(__file__), "..", "hooks", "looper-db-guard.py")


def run(cmd, sid):
    """Invoke the hook; return (denied: bool, reason: str).

    `denied` is True whenever the hook emits a deny -- that covers both a
    guard BLOCK of a write and the pseudo-command replies (arm/grant/...),
    which are also emitted as denies. Callers that specifically mean "a write
    was blocked" additionally assert 'BLOCKED' in the reason.
    """
    payload = json.dumps({
        "tool_name": "Bash",
        "session_id": sid,
        "tool_input": {"command": cmd},
    })
    out = subprocess.run([sys.executable, HOOK], input=payload,
                         capture_output=True, text=True).stdout.strip()
    if not out:
        return False, ""  # no output -> allowed (hook exited 0)
    try:
        obj = json.loads(out)["hookSpecificOutput"]
        return obj.get("permissionDecision") == "deny", obj.get("permissionDecisionReason", "")
    except Exception:
        return False, out


def blocks(cmd, sid):
    """True only when a write was BLOCKED by the guard (not a pseudo-command)."""
    denied, reason = run(cmd, sid)
    return denied and "BLOCKED" in reason


FAILURES = []


def check(desc, cond):
    status = "ok  " if cond else "FAIL"
    print(f"  [{status}] {desc}")
    if not cond:
        FAILURES.append(desc)


def main():
    # Isolate flag state so a real session's approvals never affect the run.
    tmp = tempfile.mkdtemp(prefix="looper-test-")
    os.environ["HOME"] = tmp
    sid = "sess-A"

    # Arm the guard for this session.
    denied, reason = run("looper-guard arm testslug", sid)
    print("== pseudo-command flow ==")
    check("arm returns a LOOPER-GUARD deny (deny == success)",
          denied and "ARMED" in reason)

    print("== must BLOCK: real DB/infra writes while armed ==")
    must_block = [
        ("inline DELETE",            'mysql -e "DELETE FROM users"'),
        ("inline lowercase delete",  'mysql -e "delete from users"'),
        ("stdin redirect from file", 'mysql mydb < migration.sql'),
        ("cat piped into client",    'cat migration.sql | mysql mydb'),
        ("clickhouse --queries-file",'clickhouse-client --queries-file mig.sql'),
        ("clickhouse stdin redirect",'clickhouse-client < mig.sql'),
        ("sqlite .read a file",      'sqlite3 app.db ".read migration.sql"'),
        ("sqlite stdin redirect",    'sqlite3 app.db < mig.sql'),
        ("psql inline DROP",         'psql -c "DROP TABLE users"'),
        ("psql -f file",             'psql -f mig.sql'),
        ("bare interactive mysql",   'mysql mydb'),
        ("heredoc DELETE",           'mysql mydb <<EOF\nDELETE FROM users;\nEOF'),
        ("chained read then write",  'mysql -e "SELECT 1" && mysql -e "DROP TABLE x"'),
        ("insert-select",            'clickhouse-client -q "INSERT INTO t SELECT * FROM s"'),
        ("systemctl restart",        'systemctl restart nginx'),
        ("crontab edit",             'crontab -e'),
        ("es bulk write",            'curl -XPOST http://localhost:9200/_bulk --data-binary @b.ndjson'),
    ]
    for desc, cmd in must_block:
        check(f"BLOCK: {desc}", blocks(cmd, sid))

    print("== must ALLOW: reads and harmless invocations while armed ==")
    must_allow = [
        ("inline SELECT",            'mysql -e "SELECT * FROM users"'),
        ("clickhouse -q SELECT",     'clickhouse-client -q "SELECT 1"'),
        ("clickhouse --query count", 'clickhouse-client --query "SELECT count() FROM x"'),
        ("sqlite positional SELECT", 'sqlite3 app.db "SELECT * FROM t"'),
        ("echo SELECT piped in",     'echo "SELECT 1" | clickhouse-client'),
        ("select piped to grep",     'mysql -e "SELECT * FROM t" | grep foo'),
        ("sqlite .schema dotcmd",    'sqlite3 app.db ".schema"'),
        ("client --version",         'clickhouse-client --version'),
        ("mysql --help",             'mysql --help'),
        ("unrelated command",        'ls -la /tmp'),
        ("git commit",               'git commit -m "wip"'),
    ]
    for desc, cmd in must_allow:
        check(f"ALLOW: {desc}", not blocks(cmd, sid))

    print("== grant then the write passes ==")
    run("looper-guard grant testslug", sid)
    check("after grant, opaque write is allowed",
          not blocks('mysql mydb < migration.sql', sid))

    print("== parallel-session isolation ==")
    # Session B never armed -> its writes pass even while A is armed+granted.
    check("session B (unarmed) is unaffected by session A",
          not blocks('mysql mydb < migration.sql', "sess-B"))
    # Re-arm a different session and confirm A's grant does not cover it.
    run("looper-guard arm otherslug", "sess-B")
    check("session B armed write is blocked despite A's grant",
          blocks('mysql -e "DELETE FROM t"', "sess-B"))

    print("== disarm clears the guard ==")
    run("looper-guard disarm", sid)
    check("after disarm, session A is no longer armed",
          not blocks('mysql -e "DELETE FROM users"', sid))

    print()
    if FAILURES:
        print(f"FAILED: {len(FAILURES)} case(s): {FAILURES}")
        sys.exit(1)
    print("All guard tests passed.")


if __name__ == "__main__":
    main()
