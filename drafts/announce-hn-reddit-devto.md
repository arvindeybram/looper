# Draft: announcement copy (you post these)

Pain-first framing everywhere. Do NOT link-drop. Post after v0.1.0 is tagged and
the demo GIF renders.

---

## Show HN

**Title:**
Show HN: Looper - mechanical guardrails for autonomous coding agents

**Text:**
Autonomous coding loops fail the same three ways: they declare success against
checks they invented, they quietly touch things outside the task (restart a
service, truncate a table), and they edit files with no undo.

Looper is a Claude Code plugin that answers each mechanically rather than with a
"please be careful" prompt. The plan has to include a runnable validation
contract and a list of everything it will read or write; a fresh validator runs
those checks every round instead of the executor grading its own work; every file
is snapshotted before it's edited; and a PreToolUse hook fail-closes on
database/infrastructure writes until you approve them, scoped to the session and
task.

The part I think generalizes beyond this plugin is the guard. A naive "block if
the command contains DROP/DELETE" filter is worse than nothing, because it misses
`mysql < migration.sql`, `cat x.sql | mysql`, and `clickhouse-client
--queries-file`, and sells confidence it doesn't have. So the guard is fail-closed
on DB clients: if the SQL isn't visibly a pure read, it's blocked. Coverage is an
executable test suite. Security model (including the deliberate fail-open-on-crash
behavior) is in SECURITY.md.

Repo: https://github.com/arvindeybram/looper
Would especially like feedback on write vectors the guard still misses.

**First comment (post yourself, right after):**
Background: I work in security, and the thing that made me build this was watching
an agent report "done, tests pass" after running two tests it remembered writing.
The (session_id, task-slug) scoping and the deny-as-success protocol for the
pseudo-commands are written up here: [link to the dev.to post once published].

---

## Reddit (r/ClaudeAI, r/ClaudeCode)

Post the demo GIF as the media, not a bare link. Title and body:

**Title:** I got tired of Claude Code saying "done" when it wasn't, so I built a
plan-validate loop with a mechanical DB guard

**Body:**
Three things kept biting me with autonomous runs: false "done" against invented
checks, silent blast radius (a run meant to touch one file restarting a service),
and no undo. Looper is a plugin that handles each mechanically: a fresh validator
runs a real validation contract each round, every file is backed up before it's
touched, and a hook fail-closes on database/infra writes until you approve them.

Install is `/plugin marketplace add arvindeybram/looper` then `/plugin install
looper@looper`. It's MIT, and the guard's coverage is an executable test suite.
Happy to answer questions about the guard design.

---

## dev.to / blog post

**Working title:** Deny-as-success: designing a mechanical guardrail for an
autonomous coding agent

**Angle:** the guard design specifically, which generalizes beyond this skill.
Outline:

1. The problem: prompt-level "don't touch the database" is not a control.
2. Why a keyword filter is worse than nothing (the `mysql < file.sql` class), with
   the before/after test matrix.
3. Fail-closed on DB clients: the rule is "block unless the SQL is visibly a pure
   read", and why over-blocking a read is the safe failure.
4. The pseudo-command channel: using PreToolUse deny as an RPC return value
   (deny-whose-reason-says-SUCCESS), so the skill can arm/grant/disarm through a
   hook with no extra tooling.
5. (session_id, task-slug) scoping so parallel sessions and parallel tasks don't
   leak approvals into each other.
6. The deliberate fail-open-on-crash tradeoff, and why a guard that bricks the
   shell is its own kind of failure.
7. What it is not: a seatbelt, not a vault. Adversarial evasion is out of scope.

This is the piece that gets shared; keep it about the general design, mention the
plugin once at the end.
