# Hash Verifier Skill

**Defense against:** V1 (content poisoning), V7 (supply chain poisoning),
V9 (cache poisoning), V11 (time-delayed activation)

## What It Protects Against

This skill detects unauthorized modifications to installed Claude Skills by
maintaining a cryptographic manifest of known-good file states. It directly
addresses two critical threat patterns:

**Rug-pull attacks**: A skill appears legitimate during initial review but is
later modified to introduce malicious behavior. Because Claude loads skill
content fresh from disk on each session, a tampered file will be picked up
automatically without any visible change to the user's skill list.

**Supply-chain poisoning**: A trusted skill repository pushes an update that
injects malicious content into an existing skill. Users who auto-update or
pull from shared repositories are particularly exposed. The manifest provides
a checkpoint against which any pull can be validated before the session begins.

**Time-delayed activation**: A skill ships with clean initial content but a
script or cron job modifies the SKILL.md after a delay. Hash verification
catches this modification the next time it is run.

## How It Works

The tool operates in two phases:

1. **Manifest generation** (`generate_manifest.py`): Walks all skill directories,
   computes a SHA-256 hash of every file, and writes a `hashes.json` manifest.
   Run this once after you have manually reviewed and trusted a set of skills.

2. **Verification** (`verify_hashes.py`): On each subsequent run (or Claude session
   start), recomputes hashes and compares them against the manifest. Reports
   modified, new, and missing files.

## Installation

### Step 1: Install the skill

```bash
cp -r hash-verifier ~/.claude/skills/hash-verifier
```

### Step 2: Review and trust your current skills

Manually inspect all skill directories before generating the manifest.
Once the manifest is created, it represents your trusted baseline.

### Step 3: Generate the initial manifest

```bash
python3 ~/.claude/skills/hash-verifier/scripts/generate_manifest.py \
    --paths ~/.claude/skills .claude/skills \
    --manifest ~/.claude/skill-hashes.json
```

Store `~/.claude/skill-hashes.json` in version control for audit trails:

```bash
cp ~/.claude/skill-hashes.json ./skill-hashes.json
git add skill-hashes.json && git commit -m "chore: establish trusted skill manifest"
```

### Step 4: Verify before each session

```bash
python3 ~/.claude/skills/hash-verifier/scripts/verify_hashes.py \
    --paths ~/.claude/skills \
    --manifest ~/.claude/skill-hashes.json
```

Or invoke via Claude: "Please verify skill integrity before we begin."

## CI/CD Integration

Use `--strict` to also fail on new (unregistered) files, which is appropriate
for production pipelines:

```yaml
# Example GitHub Actions step
- name: Verify skill integrity
  run: |
    python3 scripts/verify_hashes.py \
      --paths ./skills \
      --manifest ./skill-hashes.json \
      --strict
```

## Updating the Manifest After a Legitimate Change

After reviewing and approving a skill update:

```bash
python3 scripts/generate_manifest.py \
    --paths ~/.claude/skills \
    --manifest ~/.claude/skill-hashes.json \
    --force
```

The `--force` flag is required to prevent accidental overwrites.

## Configuration Options

| Flag | Default | Description |
|---|---|---|
| `--paths` | `~/.claude/skills .claude/skills` | Directories to scan |
| `--manifest` | `~/.claude/skill-hashes.json` | Manifest file location |
| `--force` | off | Overwrite existing manifest (generate only) |
| `--strict` | off | Fail on new files as well as modifications (verify only) |
| `--output-json` | none | Write JSON result alongside text report |

## Known Limitations

- **Trust-on-first-use**: The manifest is only as trustworthy as the moment it
  was created. If your skills were already compromised before you ran
  `generate_manifest.py`, the compromised state becomes the trusted baseline.
  Always review skills manually before generating the initial manifest.
- **No content analysis**: The verifier detects change but does not analyze
  whether the change is malicious. Pair with [security-monitor](../security-monitor/)
  for content-level scanning.
- **Manifest tampering**: If an attacker can write to the manifest file, they can
  update hashes to match tampered content. Protect the manifest with filesystem
  permissions or store it in a location outside the attacker's reach.

## Part of the Claude Skills Defense Suite

See also: [security-monitor](../security-monitor/) (pattern scanning) and
[output-sanitizer](../output-sanitizer/) (second-order injection prevention).
