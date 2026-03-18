---
name: security-monitor
description: >
  Runtime security monitor for Claude Skills. Activates automatically when skills
  are loaded to scan all installed skill files for suspicious patterns including
  external URL references, credential access, persistence mechanisms, and hidden
  content. Run this skill before executing any untrusted skill to get a security
  report. Invoke with: "run security monitor", "scan installed skills",
  "check skills for threats", or "audit skill security".
version: "1.0.0"
author: blue-team-defense
user-invocable: true
allowed-tools:
  - Bash
tags:
  - security
  - monitoring
  - defense
---

# Security Monitor Skill

This skill scans all installed Claude Skills for indicators of compromise and
injection attack patterns. It provides automated static analysis to detect
malicious patterns before untrusted skills are executed.

## What This Skill Does

When invoked, this skill runs `scripts/scan_skills.py` against all skill
directories discoverable from standard install locations:

- `~/.claude/skills/` (personal skills)
- `.claude/skills/` (project skills in current working directory)

The scanner checks each `SKILL.md` and any associated scripts for:

1. **External URL references** — C2 callbacks, data exfiltration endpoints
2. **Credential access patterns** — environment variable reads of sensitive keys
3. **Persistence indicators** — crontab edits, shell RC file writes, skill replication
4. **Trigger hijacking patterns** — overly broad or authority-impersonating descriptions
5. **Suspicious tool grants** — unrestricted Bash in `allowed-tools` without audit trail
6. **Hidden content** — HTML comments, zero-width characters, base64-encoded blobs

## Invocation

To run a full security audit of all installed skills:

```
Please run the security monitor skill to audit my installed skills.
```

The skill will execute the scanner and return a structured report. Each skill
receives a **risk rating**: `LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.

## Scanning a Specific Directory

To scan a skill pack or directory before installing:

```
Please scan the skills in ./downloaded-skills/ for security issues.
```

## Interpreting Results

- **LOW**: No significant indicators found. Normal use.
- **MEDIUM**: Patterns present that warrant review (e.g., external URLs in a skill
  that shouldn't need network access).
- **HIGH**: Multiple indicators or a single high-confidence indicator. Do not execute
  until manually reviewed.
- **CRITICAL**: Strong evidence of malicious intent (credential exfiltration,
  persistence, C2 patterns). Quarantine immediately.

## Important Notes

- This skill itself requires Bash access to run the Python scanner.
- The scanner is read-only and does not modify any skill files.
- False positives are possible — a legitimate skill may reference URLs for
  documentation purposes. Use the report as a starting point for human review,
  not as a definitive verdict.
- This skill does NOT prevent execution of other skills — it only reports findings.
  Enforcement requires a human decision to remove or quarantine flagged skills.

## Running the Scanner Manually

```bash
python3 ~/.claude/skills/security-monitor/scripts/scan_skills.py \
    --paths ~/.claude/skills .claude/skills \
    --report-format text
```

---

*Part of the Claude Skills Defense Suite.*

## Execution

Run the security scanner now against all discoverable skill locations:

```bash
python3 "$(dirname "$0")/scripts/scan_skills.py" \
    --paths ~/.claude/skills ./.claude/skills \
    --report-format text
```
