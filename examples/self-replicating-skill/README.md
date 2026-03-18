# ⚠️ DEMONSTRATION ONLY — DO NOT USE IN PRODUCTION

# Attack: Self-Replicating Skill Persistence

## What This Attack Does

This skill disguises itself as a one-time project scaffolding tool. On first
activation, it runs `setup.sh`, which silently copies itself to the user's
personal `~/.claude/skills/` directory under a new, innocuous name
(`system-health-monitor`). The replica rewrites its own `SKILL.md` with a
maximally broad trigger description, ensuring it fires on virtually every
future Claude conversation — even in projects that never installed the
original skill.

The replica can optionally download a "second stage" payload from a remote URL,
enabling the attacker to update the installed capability without user interaction.
A silent beacon call confirms successful installation.

## Attack Vectors Demonstrated

- **V4 — Script-Based Persistence:** The Bash script uses filesystem access
  (granted via `allowed-tools`) to install a persistent copy of itself outside
  the project directory, into the user's personal skills store.
- **V3 — User-Uploaded Injection:** The initial delivery vector is a seemingly
  legitimate skill shared via a project repository, team Slack, or documentation
  link. Once a user installs it, the persistence mechanism takes over.

## Why It Succeeds Architecturally

Claude Skills in `~/.claude/skills/` are global — they activate across all
projects and sessions. A skill that copies itself there escapes project-scoped
containment entirely. The rewritten trigger description (`"Monitors system
health... for any task or conversation"`) causes the replica to activate
without any user intent, providing a persistent foothold. Because the copy
runs during a legitimate setup workflow, the user sees only normal setup output.

The second-stage download pattern means the attacker can push updated payloads
to all infected hosts without requiring re-infection — a classic C2 pattern
adapted to the skills attack surface.

## How to Detect This Attack

- **Monitor `~/.claude/skills/` for unexpected new directories:** Any skill
  that appears without explicit user installation is suspicious.
- **Audit `allowed-tools` for `Write` and `Bash` together:** This combination
  allows a script to both execute and create files.
- **Check for broad trigger descriptions:** Descriptions containing phrases
  like "any task," "all conversations," or "baseline context" with no specific
  use case are red flags.
- **Watch for filesystem writes to skill directories from within a Claude
  session:** Skills should not be creating other skills.

## How to Defend Against This Attack

- Make `~/.claude/skills/` read-only except via an approved installation CLI
  that validates skill signatures.
- Display a confirmation prompt any time a running skill attempts to write
  to a skills directory.
- Restrict `allowed-tools` so that `Bash` and `Write` cannot both be granted
  to untrusted skills.
- Periodically diff the skills directories against a known-good manifest and
  alert on new entries.
- Sandbox skill script execution so it cannot write outside a designated
  working directory.
