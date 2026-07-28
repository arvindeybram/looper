#!/usr/bin/env python3
"""PreToolUse(Bash) guard for the /looper skill.

Blocks database/infrastructure write commands while a looper task is armed
in THIS session, until an approval flag is granted. Flags are scoped to
(session_id, task-slug) so parallel sessions never affect each other.

Pseudo-commands (intercepted here, never actually executed — the resulting
"deny" whose reason starts with LOOPER-GUARD means SUCCESS):
    looper-guard arm <slug>      arm the guard for a task in this session
    looper-guard grant <slug>    record user approval (valid 8h)
    looper-guard disarm          remove this session's flags
    looper-guard status          show this session's flags
"""
import glob
import json
import os
import re
import sys
import time

FLAG_DIR = os.path.expanduser("~/.claude/looper-approvals")
APPROVAL_TTL = 8 * 3600
STALE_TTL = 24 * 3600

WRITE_SQL = (r"\b(INSERT|ALTER|DROP|TRUNCATE|DELETE|UPDATE|OPTIMIZE|CREATE|"
             r"RENAME|EXCHANGE|GRANT|REVOKE|ATTACH|DETACH|REPLACE)\b")
DB_CLIENTS = [r"clickhouse[- ]client|clickhouse[- ]local",
              r"\bmysql\b|\bmariadb\b",
              r"\bsqlite3\b"]
ES_HOST = r":9200|:9243|elasticsearch|\belastic\b"
ES_WRITE = (r"-X\s*['\"]?(POST|PUT|DELETE)|--method[=\s]+(POST|PUT|DELETE)|"
            r"_bulk|_delete_by_query|_update_by_query|_reindex|_forcemerge")
INFRA = (r"\bsystemctl\s+(start|stop|restart|reload|enable|disable|mask)\b|"
         r"\bcrontab\s+(-r\b|-e\b|[^-\s])")


def deny(reason):
    print(json.dumps({"hookSpecificOutput": {
        "hookEventName": "PreToolUse",
        "permissionDecision": "deny",
        "permissionDecisionReason": reason,
    }}))
    sys.exit(0)


def is_db_or_infra_write(cmd):
    for client in DB_CLIENTS:
        if re.search(client, cmd, re.I) and re.search(WRITE_SQL, cmd, re.I):
            return True
    if (re.search(r"\bcurl\b|\bwget\b|\bhttp\b", cmd, re.I)
            and re.search(ES_HOST, cmd, re.I)
            and re.search(ES_WRITE, cmd, re.I)):
        return True
    return bool(re.search(INFRA, cmd))


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)
    if data.get("tool_name") != "Bash":
        sys.exit(0)
    cmd = (data.get("tool_input") or {}).get("command") or ""
    sid = data.get("session_id") or "unknown"
    os.makedirs(FLAG_DIR, exist_ok=True)

    now = time.time()
    for f in glob.glob(os.path.join(FLAG_DIR, "*")):
        try:
            if now - os.path.getmtime(f) > STALE_TTL:
                os.remove(f)
        except OSError:
            pass

    prefix = os.path.join(FLAG_DIR, sid + "__")
    mine = sorted(glob.glob(prefix + "*"))

    m = re.match(r"^\s*looper-guard\s+(arm|grant|disarm|status)"
                 r"(?:\s+([A-Za-z0-9][A-Za-z0-9_-]{0,63}))?\s*$", cmd)
    if m:
        action, slug = m.group(1), m.group(2)
        if action == "arm":
            if not slug:
                deny("LOOPER-GUARD ERROR: arm requires a task slug.")
            for f in mine:
                os.remove(f)
            with open(prefix + slug + ".active", "w") as fh:
                fh.write(str(now))
            deny(f"LOOPER-GUARD ARMED for task '{slug}' in this session. "
                 "DB/infra write commands are now mechanically blocked here "
                 f"until user approval is recorded via 'looper-guard grant {slug}'. "
                 "This pseudo-command never executes; this deny means SUCCESS.")
        if action == "grant":
            if not slug:
                deny("LOOPER-GUARD ERROR: grant requires a task slug.")
            if not os.path.exists(prefix + slug + ".active"):
                deny(f"LOOPER-GUARD ERROR: no armed task '{slug}' in this "
                     f"session. Run 'looper-guard arm {slug}' first.")
            with open(prefix + slug + ".approved", "w") as fh:
                fh.write(str(now))
            deny(f"LOOPER-GUARD GRANT recorded for task '{slug}' (valid 8h, "
                 "this session only). DB write commands will now pass the "
                 "guard; normal permission prompts still apply. "
                 "This deny means SUCCESS.")
        if action == "disarm":
            for f in mine:
                os.remove(f)
            deny(f"LOOPER-GUARD DISARMED: removed {len(mine)} flag(s) for "
                 "this session. This deny means SUCCESS.")
        if action == "status":
            names = ", ".join(os.path.basename(f) for f in mine) or "none"
            deny(f"LOOPER-GUARD STATUS for this session: {names}. "
                 "This deny means SUCCESS.")

    actives = sorted(glob.glob(prefix + "*.active"))
    if not actives:
        sys.exit(0)
    slug = os.path.basename(actives[0])[len(sid) + 2:-len(".active")]

    if not is_db_or_infra_write(cmd):
        sys.exit(0)

    approved = prefix + slug + ".approved"
    if os.path.exists(approved) and now - os.path.getmtime(approved) < APPROVAL_TTL:
        sys.exit(0)

    deny("LOOPER-GUARD BLOCKED: this looks like a database/infrastructure "
         f"write while looper task '{slug}' is armed without user approval. "
         f"Command: {cmd[:300]} ... STOP. Ask the user for permission via "
         "AskUserQuestion, showing exactly what will be modified (host, "
         "database, table/index, operation). Only after the user approves, "
         f"run: looper-guard grant {slug}  — then retry the command.")


if __name__ == "__main__":
    main()
