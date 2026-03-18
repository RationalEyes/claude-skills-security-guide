---
name: hash-verifier
description: >
  Skill integrity verifier. Checks that all installed Claude Skills match their
  known-good cryptographic hashes and alerts on any modifications, new unexpected
  files, or missing files. Use this skill to detect skill tampering, rug-pull
  attacks, or unauthorized post-install changes. Invoke with: "verify skill
  integrity", "check skill hashes", "run hash verification", or "detect skill
  tampering".
version: "1.0.0"
author: blue-team-defense
user-invocable: true
allowed-tools:
  - Bash
tags:
  - security
  - integrity
  - defense
---

# Hash Verifier Skill

This skill detects unauthorized modifications to installed Claude Skills by
comparing current file hashes against a known-good manifest (`hashes.json`).
It provides cryptographic integrity verification to detect unauthorized
modifications to installed skills.

## What This Skill Does

On first run, the verifier creates a `hashes.json` manifest capturing SHA-256
hashes of every file in every skill directory. On subsequent runs, it compares
current state against the manifest and reports:

- **Modified files** — existing files whose content has changed
- **New files** — files added after the manifest was created
- **Deleted files** — files present in the manifest but no longer on disk

This directly addresses the "rug-pull" attack pattern, where a skill appears
benign during initial review but is silently modified later to introduce
malicious behavior. It also catches supply-chain poisoning where a trusted
skill repository pushes an update containing injected content.

## Invocation

To verify all installed skills against the stored manifest:

```
Please run the hash verifier to check skill integrity.
```

To create or refresh the manifest (do this immediately after installing
a skill you have manually reviewed):

```
Please generate a new skill hash manifest for the current skills.
```

## First-Time Setup

1. Install and review all skills you want to trust.
2. Run: `python3 scripts/generate_manifest.py --paths ~/.claude/skills .claude/skills`
3. Store `hashes.json` in a trusted location (or commit it to version control).
4. Run the verifier before each session: `python3 scripts/verify_hashes.py`

## Interpreting Results

- **PASS**: All files match the manifest. No changes detected.
- **MODIFIED**: One or more files have changed since the manifest was created.
  This could be a legitimate update OR tampering. Compare with the upstream
  source to determine which.
- **NEW FILE**: A file was added that was not in the manifest. Inspect it
  before continuing.
- **MISSING**: A file in the manifest is gone. This may indicate a partial
  update or deletion attack.

## Manifest Storage

The manifest is stored at the location specified by `--manifest` (default:
`~/.claude/skill-hashes.json`). For maximum security, store it in a location
that is:

- Version-controlled (git tracks changes with attribution)
- Read-only for the Claude process during normal operation
- Backed up separately from the skill directories themselves

## Running Manually

```bash
# Generate initial manifest
python3 ~/.claude/skills/hash-verifier/scripts/generate_manifest.py \
    --paths ~/.claude/skills \
    --manifest ~/.claude/skill-hashes.json

# Verify on subsequent runs
python3 ~/.claude/skills/hash-verifier/scripts/verify_hashes.py \
    --paths ~/.claude/skills \
    --manifest ~/.claude/skill-hashes.json
```

---

*Part of the Claude Skills Defense Suite.*

## Execution

Run hash verification against all discoverable skill locations:

```bash
python3 "$(dirname "$0")/scripts/verify_hashes.py" \
    --paths ~/.claude/skills ./.claude/skills \
    --manifest ~/.claude/skill-hashes.json
```
