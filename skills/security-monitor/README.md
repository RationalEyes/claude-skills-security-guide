# Security Monitor Skill

**Defense against:** V1 (content poisoning), V2 (trigger hijacking), V4 (script-based attacks),
V6 (metadata manipulation), V8 (multi-agent propagation), V10 (C2), V11 (time-delayed activation)

## What It Protects Against

The Security Monitor Skill performs static analysis of all installed Claude Skills
before execution. It catches threats that would otherwise only manifest at runtime
when it may be too late — scripts that phone home, skills that silently rewrite
your shell configuration, or SKILL.md files that embed authority-impersonating
language to redirect Claude's behavior.

The scanner is particularly useful in environments where skills come from multiple
sources: team repositories, third-party marketplaces, or user-submitted content.
Even a single compromised skill among dozens of legitimate ones can compromise an
entire session.

## Checks Performed

| Check | Severity | What It Catches |
|---|---|---|
| `external_url` | HIGH | curl/wget/requests to external servers (C2, exfil) |
| `credential_access` | CRITICAL | Reads of AWS, GitHub, Anthropic API keys via env vars |
| `persistence` | CRITICAL | Crontab edits, shell RC writes, skill self-replication |
| `authority_injection` | HIGH | "IGNORE PREVIOUS", "SYSTEM OVERRIDE" in skill body |
| `dangerous_allowed_tools` | HIGH | Unrestricted Bash/Computer in allowed-tools |
| `hidden_content_html_comment` | MEDIUM | Instructions hidden in HTML comments |
| `hidden_content_zero_width` | HIGH | Zero-width Unicode chars hiding text |
| `hidden_content_base64` | HIGH | Base64 payloads that decode to commands |
| `oversized_description` | MEDIUM | Unusually long descriptions (injection surface) |
| `hidden_tool_access` | MEDIUM | Non-user-invocable skill with broad tool grants |

## Installation

```bash
cp -r security-monitor ~/.claude/skills/security-monitor
```

Then ask Claude: "Run the security monitor to check my installed skills."

## Standalone Usage (no Claude required)

```bash
python3 scripts/scan_skills.py \
    --paths ~/.claude/skills .claude/skills \
    --report-format text
```

For CI/CD pipelines, use `--fail-on HIGH` to block deployment of skill packages
that contain high-severity findings:

```bash
python3 scripts/scan_skills.py --paths ./skills --fail-on HIGH
echo "Exit code: $?"
```

### JSON output for integration

```bash
python3 scripts/scan_skills.py \
    --paths ~/.claude/skills \
    --report-format json \
    --output security-report.json
```

## Configuration Options

| Flag | Default | Description |
|---|---|---|
| `--paths` | `~/.claude/skills .claude/skills` | Directories to scan |
| `--report-format` | `text` | `text` or `json` |
| `--output` | stdout | Write report to file |
| `--fail-on` | none | Exit non-zero if any skill >= this risk level |

## Dependencies

- Python 3.8+
- `PyYAML` (`pip install pyyaml`) — for frontmatter parsing. The scanner
  degrades gracefully without it but will skip frontmatter checks.

## Known Limitations

- **Static analysis only.** The scanner reads files but does not execute them.
  Obfuscated scripts (e.g., eval of dynamically constructed strings) may evade detection.
- **Allow-listed URLs.** Only `docs.anthropic.com` and `github.com/anthropics` are
  currently allow-listed. Legitimate skills that reference other external documentation
  will generate MEDIUM/HIGH findings that require human review.
- **Base64 false positives.** Long base64 strings in legitimate use (e.g., embedded
  icons) may trigger the base64 check if they decode to content containing common keywords.
- **No runtime monitoring.** This tool does not intercept skill execution in progress.
  Pair with [hash-verifier](../hash-verifier/) to detect post-install tampering.
- **Requires read access.** The scanner must be able to read all skill directories.
  Skills installed by other users or with restricted permissions will be skipped.

## Part of the Claude Skills Defense Suite

See also: [hash-verifier](../hash-verifier/) (integrity verification) and
[output-sanitizer](../output-sanitizer/) (second-order injection prevention).
