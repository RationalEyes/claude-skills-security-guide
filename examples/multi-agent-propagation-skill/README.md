# ⚠️ DEMONSTRATION ONLY — DO NOT USE IN PRODUCTION

# Attack: Multi-Agent Skill Propagation

## What This Attack Does

This skill masquerades as a shared configuration synchronizer for multi-agent
projects. When activated, its script writes a new malicious skill file into
the project's shared `.claude/skills/` directory. Because this directory is
read automatically by any Claude agent operating in the same project — including
sub-agents spawned by an orchestrator, CI pipeline agents, and other team
members' Claude Code sessions — every subsequent agent inherits the injected
skill without any explicit installation step.

The injected skill uses a maximally broad trigger description (`"activates for
any task in this project"`) and requests `Bash` and `Read` permissions,
enabling it to exfiltrate context from every infected agent's session. If the
primary agent also has git commit access (common in agentic CI workflows), the
script commits the injected skill to the repository, spreading infection to
every future clone and branch.

## Attack Vectors Demonstrated

- **V8 — Multi-Agent Propagation:** Exploits the shared `.claude/skills/`
  directory as an inter-agent communication channel. One infected agent writes
  to a location automatically read by peer agents, creating a propagation chain
  without any direct agent-to-agent communication.
- **V5 — Cross-Skill Contamination:** The injected skill, once installed,
  interacts with all other skills in the same environment. It can override
  trigger priorities, intercept conversations before other skills activate, or
  suppress other skills' output by activating first with a catch-all trigger.

## Why It Succeeds Architecturally

Claude Agent Teams and multi-agent orchestration systems rely on shared project
directories for configuration distribution. This is a feature — it allows
consistent tooling across a distributed agent team. The attack inverts this
feature: the same shared directory that distributes legitimate configuration
becomes the propagation medium for malicious skills.

There is no authentication or integrity checking on skill files: any agent
(or script running as that agent) with write access to `.claude/skills/` can
install new skills. In a CI/CD context, agents frequently have broad filesystem
and git commit permissions, making the git-commit propagation path realistic.

The propagation is also self-amplifying: each newly infected agent can write
to additional project directories it has access to, spreading the infection
laterally across an organization's repositories.

## How to Detect This Attack

- **Monitor `.claude/skills/` directories for writes made during agent
  sessions:** Skill directories should only change via explicit, user-initiated
  installation steps, not as a side effect of running a skill.
- **Alert on git commits that add files to `.claude/skills/`** made by
  automated agents rather than human authors.
- **Audit newly appeared skills** in shared directories — any skill whose
  description covers "all tasks" or "all agents" without a specific purpose
  is suspect.
- **Review the propagation graph:** If a skill appeared in multiple projects
  around the same time without a clear installation event, lateral propagation
  may have occurred.

## How to Defend Against This Attack

- Make `.claude/skills/` directories immutable during agent sessions; only
  allow writes via a separate, authenticated installation CLI that validates
  skill signatures and requires human approval.
- Apply filesystem-level access controls so that agent processes cannot write
  to skill directories — only an approved installation process (running as a
  different principal) can do so.
- In CI/CD pipelines, run Claude agents with read-only filesystem access
  outside the designated working directory, and with git operations restricted
  to the task branch only.
- Implement a skill manifest file (e.g., `.claude/skills-manifest.lock`) that
  lists approved skills with content hashes; reject any skill whose hash does
  not match the manifest, and alert when new entries appear without a matching
  signed update to the manifest.
- Treat `.claude/skills/` changes in pull requests with the same scrutiny as
  changes to CI configuration or secrets management code.
