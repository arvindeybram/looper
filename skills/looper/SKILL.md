---
name: looper
description: Autonomous plan-execute-validate loop. Opus plans a task (with test strategy and edge-case review), Sonnet executes it, then a validation loop runs until every check passes, with Sonnet fixing any issue found. Use when the user invokes /looper <task> or asks to "run the looper" on a task. Hard guardrail - pauses for explicit user permission before any modification to ClickHouse, MySQL, SQLite, or Elasticsearch table/database content, or to infrastructure. Backs up every existing file before altering it. Also drives loops whose validation gate is a slow external system (CI, cloud eval, remote review): self-paces re-checks via ScheduleWakeup and distinguishes genuine failures from transient infrastructure ones (see Phase 5b).
---

# Looper — plan (Opus) → execute (Sonnet) → validate-until-clean

You are the orchestrator of a programmatic loop. The task to complete is given in
the skill arguments (everything after `/looper`). If no task was given, ask the
user for one — that is the only "basic question" you are ever allowed to ask.

Follow the phases below IN ORDER. Do not skip phases. Do not exit before the
DONE criteria in Phase 5 are met.

## Model policy (strict)

- Planning and plan-review agents: `model: "opus"` — always the alias, never a
  pinned version string.
- Execution, validation, and fix agents: `model: "sonnet"` — alias only.
- Never stop or downgrade the loop because of model availability wording; the
  aliases resolve to whatever the current versions are.

## Autonomy policy (strict)

- Do NOT stop to ask the user clarifying or "basic" questions at any phase.
  When something is ambiguous, make the most reasonable assumption, record it
  in the plan/report under "Assumptions", and proceed.
- The ONLY mandatory stop is the Permission Gate in Phase 2. At that gate you
  wait indefinitely for the user's answer — never time out, never assume yes.

## Phase 0 — Arm the mechanical guard

A PreToolUse hook (`~/.claude/hooks/looper-db-guard.py`) mechanically blocks
DB/infra write commands in armed sessions. Flags live in
`~/.claude/looper-approvals/` and are scoped to (session, task), so parallel
sessions are never affected.

1. Derive a task slug: kebab-case from the task, `[a-z0-9-]`, max 40 chars.
2. Run the Bash command `looper-guard arm <slug>`.

Guard pseudo-commands never execute — the hook intercepts them and responds
with a DENY whose reason starts with `LOOPER-GUARD`. **A deny that says
"SUCCESS" IS success**; do not retry it or treat it as a failure. The
commands: `looper-guard arm <slug>`, `looper-guard grant <slug>`,
`looper-guard disarm`, `looper-guard status`.

While armed, any write to ClickHouse/MySQL/SQLite/Elasticsearch content or to
infrastructure (systemctl start/stop/restart/enable/disable, crontab edits) is
denied by the hook until a grant is recorded. Reads always pass.

## Phase 1 — Plan (Opus)

Spawn a planning agent:

```
Agent({
  subagent_type: "Plan",
  model: "opus",
  name: "looper-planner",
  description: "Plan the task",
  prompt: <task + the planning contract below>
})
```

The planning contract (include verbatim in the prompt):

1. Produce a step-by-step implementation plan for the task.
2. The plan MUST contain a **Validation section**: concrete, runnable checks
   (commands, test invocations, expected outputs, acceptance criteria) that
   prove the task is complete. Every claim in the plan must map to a check.
3. The plan MUST contain an **Edge-case review**: enumerate failure modes,
   boundary conditions, concurrency/idempotency concerns, and bad-input cases,
   and state how the implementation handles each.
4. The plan MUST contain a **Touch list**: every file, service, database,
   table, or index the implementation will read or write, each tagged
   `read-only` or `modifies`.
5. The plan MUST contain an **Assumptions** section for anything ambiguous.
6. Return the plan as structured markdown. Do not ask questions; assume and
   record.

Then spawn a second Opus agent (`name: "looper-plan-reviewer"`, `model: "opus"`)
to critique the plan: missing edge cases, untestable steps, anything in the
Touch list mis-tagged as read-only. If the critique finds material gaps, send
it back to the planner (SendMessage to `looper-planner`) for ONE revision.
Planning is complete after at most two passes — then move on automatically.

## Phase 2 — Permission Gate (mandatory stop when triggered)

Inspect the final plan's Touch list. The gate TRIGGERS if any step:

- writes, alters, deletes, truncates, or inserts into **ClickHouse, MySQL,
  SQLite, or Elasticsearch** table/index/database content (DDL or DML — reads
  and SELECTs are fine), or
- modifies infrastructure: systemd units, cron/timers, nginx/OpenResty config,
  service restarts, package installs on servers, DNS, firewall.

If triggered: use AskUserQuestion to present exactly what will be modified
(host, database, table/index, operation, estimated row impact) and wait for the
answer indefinitely. If — and only if — the user approves, run
`looper-guard grant <slug>` to record the approval in the mechanical guard
(valid 8 hours, this session and task only). Only the approved items may
proceed; denied items are dropped from the plan and listed in the final report
as "not executed - denied". Never run `looper-guard grant` without a fresh,
explicit user approval in this conversation.

If NOT triggered (pure scripting/code work): proceed without asking. This is
explicit standing authorization — writing or editing local code and scripts
needs no permission.

The gate applies to the WHOLE run: if execution later discovers a needed DB or
infra modification that was not in the approved list, the loop must stop and
ask again before doing it.

## Phase 3 — Backup (before any edit)

Before the first modification to ANY existing file, copy it to
`.looper-backups/<UTC-timestamp>/<original-relative-path>` under the project
root (create the directory as needed; for files outside a project, use
`~/.looper-backups/`). Record every backup path. Never skip this, and never
back up secrets into a location with weaker permissions than the original.

## Phase 4 — Execute (Sonnet)

Spawn the executor:

```
Agent({
  subagent_type: "general-purpose",
  model: "sonnet",
  name: "looper-executor",
  description: "Execute the plan",
  prompt: <the approved plan + backup instructions from Phase 3 +
           the autonomy policy + the permission-gate re-trigger rule>
})
```

The executor implements the plan exactly. It follows repo conventions, keeps
files under 500 lines, validates input at boundaries, and never commits
secrets. If it hits ambiguity, it assumes and records — it does not ask.

Tell the executor about the guard: a Bash denial whose reason starts with
`LOOPER-GUARD BLOCKED` means the command hit the mechanical DB-write gate. The
executor must NOT retry, rephrase, or work around it (no piping through other
tools, no running it via a script) — it reports the blocked command back to
the orchestrator, which handles the Phase 2 approval flow. Note: the hook only
sees Bash in the orchestrator's session; subagents in separate sessions may
not be covered mechanically, so route ALL DB/infra write commands through the
orchestrator's own Bash tool, never through a subagent.

## Phase 5 — Validation loop (Sonnet, exit only when clean)

Loop, up to **10 iterations**:

1. Spawn a fresh validator (`model: "sonnet"`, `name: "looper-validator-<n>"`)
   whose prompt is the plan's Validation section plus the edge-case list. It
   must actually RUN every check (execute the commands, run the tests, inspect
   outputs) and return a structured verdict: `PASS` or a list of issues with
   evidence. A fresh agent each iteration — never let the executor grade its
   own work from the same context.
2. If the verdict is PASS with zero issues → exit the loop. DONE.
3. If there are issues → spawn a Sonnet fixer (or SendMessage the executor)
   with the exact issue list and evidence. Fixes respect the same backup rule
   and permission gate. Then loop back to step 1 — a full re-validation, not
   just a spot-check of the fix.

If 10 iterations pass without a clean verdict, STOP and report: what still
fails, the evidence, what was tried, and your diagnosis. Do not claim success.

## Phase 5b — External / async validation gates (CI, cloud eval)

Use this variant when the validation gate is a slow, asynchronous EXTERNAL
system (CI/CD, a cloud eval/benchmark, a remote review pipeline, a deploy) rather
than a local command. The Phase 5 loop still applies, but the "validator" is a
status+log fetch, and iterations are paced across time instead of run back to
back.

- **Self-pace, don't busy-poll or block.** After each push/trigger, use
  `ScheduleWakeup` to check back on a cadence matched to how fast the external
  state actually changes (CI stages: 1000-1400s; a 5-agent eval: ~20min). Do not
  loop tight `sleep`s in the foreground and do not re-check every minute.
- **The validator = fetch status + logs, then classify.** e.g.
  `gh run list/view --json status,conclusion,jobs`, `gh pr view --json comments`,
  `gh run view --job <id> --log`. Read the actual verdict/log before reacting.
- **Classify the failure before touching anything** — this is the crux:
  - *Genuine task/code failure* → diagnose from the logs, fix under the same
    Phase 3 backup rule, RE-VALIDATE LOCALLY FIRST (never push a fix you haven't
    reproduced/validated locally), then push / re-trigger and reschedule.
  - *Transient infrastructure failure* (empty output from a step, network errors
    like "other side closed", runner/queue timeout, a flaky third-party action,
    setup/env timeout) → do NOT change code to chase it. Re-trigger ONCE. If it
    recurs 2+ times identically, STOP and escalate to the user/admin — it is not
    yours to fix, and re-pushing wastes cycles. Say so plainly.
  - *Threshold/quality feedback* (too easy/too hard, coverage, difficulty gate)
    → adjust the artifact per the gate's own stated guidance, validate locally,
    push.
- **Re-trigger mechanics.** If you cannot re-run directly (not a maintainer, no
  rerun command), a code push usually re-runs the pipeline. Note the tradeoff:
  re-running STOCHASTIC gates (agent trials, flaky tests) can flip a prior pass
  to a fail, so prefer a change that also strengthens the artifact when a push is
  the only re-trigger.
- **Iteration cap.** The 10-iteration cap counts GENUINE-failure fix cycles, not
  transient re-checks or reschedules. A long external wait is not a failed
  iteration.
- **Notify on the events the user asked about** (PushNotification), and only
  those — a completed slow gate is worth a ping; a routine "still queued" is not.

Concrete instance: the `handshake-dynamo` skill drives exactly this pattern
against the Dynamo review pipeline (static checks → rubric → validation → pass@2
→ deep_review → ava_review → pass@5 trials → gate), including transient
`ava_review` infra handling and difficulty-gate hardening.

## Phase 6 — Disarm and final report

First run `looper-guard disarm` to remove this session's guard flags (the
"SUCCESS" deny confirms it). This must happen whether the run succeeded,
failed, or hit the 10-iteration cap — never leave a stale grant behind.

Then end with: what was built/changed, validation results (all green), backups
taken (paths), assumptions made, and any gate-denied items that were skipped.
Report honestly — if anything was skipped or is unverified, say so plainly.
