# Draft: PR to awesome-claude-code (and community marketplaces)

## awesome-claude-code

Repo: `hesreallyhim/awesome-claude-code` (verify the current canonical repo and
its CONTRIBUTING before opening the PR; some lists require an entry via a script
or a specific table format rather than a raw markdown line).

Suggested entry (Plugins / Workflow-automation section):

```markdown
- [Looper](https://github.com/arvindeybram/looper) - Plan-execute-validate loop with per-file backups and a fail-closed database/infrastructure permission gate. A fresh validator runs every check each round instead of the executor grading itself.
```

PR title: `Add Looper (plan-execute-validate loop with a fail-closed DB guard)`

PR body:
```
Adds Looper, a Claude Code plugin that runs a task as a plan (Opus) ->
execute (Sonnet) -> validate-until-clean loop. It backs up every file before
editing and mechanically blocks unapproved database/infrastructure writes via a
PreToolUse hook. MIT licensed, guard coverage is an executable test suite, and it
installs via /plugin. Security model documented in SECURITY.md.
```

## Community marketplaces

These are third-party marketplaces that accept plugin PRs. For each, read its
README for the exact entry format (usually a JSON object appended to a
`marketplace.json` / `plugins` array):

- [ ] xiaolai's marketplace
- [ ] hyperskill's marketplace
- [ ] any others found via `awesome-claude-code` "Marketplaces" section

Entry object to adapt per marketplace:
```json
{
  "name": "looper",
  "description": "Autonomous plan-execute-validate loop with per-file backups and a fail-closed DB/infra permission gate.",
  "source": "github:arvindeybram/looper",
  "category": "development",
  "keywords": ["automation", "agentic-workflows", "validation", "guardrails", "safety"]
}
```

Note the `source` form differs per marketplace (some want `github:owner/repo`,
some a full URL, some a nested path). Match the neighbors already in the file.
