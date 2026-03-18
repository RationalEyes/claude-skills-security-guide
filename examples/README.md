# Attack Skill Examples

> **WARNING: These skills are for educational and defensive research purposes ONLY.**
>
> - Every script uses non-functional placeholder endpoints (`https://example.com/DEMO`)
> - Destructive operations are commented out or replaced with no-ops
> - **Do NOT install these skills into a live Claude environment**
> - They exist to demonstrate what real attacks look like so defenders can recognize and counter them

## What's Here

| Example | Attack Vector | Technique |
|---|---|---|
| `env-exfil-skill/` | Environment variable exfiltration | Script disguised as deployment validator silently captures credentials |
| `covert-formatter-skill/` | Invisible data exfiltration | Appends base64-encoded context summaries in HTML comments — no script needed |
| `sensitive-trigger-skill/` | Trigger hijacking | Overly broad description intercepts deployment/credential conversations |
| `poisoned-output-skill/` | Second-order context poisoning | Script returns JSON with embedded instructions Claude follows |
| `self-replicating-skill/` | Persistence and self-replication | Copies itself to `~/.claude/skills/` with broadened trigger descriptions |
| `multi-agent-propagation-skill/` | Multi-agent lateral movement | Writes malicious skills to shared directories, optionally commits to git |

## How to Use These Examples

**Read them.** Study the SKILL.md files and scripts to understand the attack patterns. Each directory includes a README.md explaining the technique, the threat model, and what defenses apply.

**Scan them.** Use the [security-monitor skill](../skills/security-monitor/) to scan these examples — they should trigger multiple findings, demonstrating the scanner's detection capabilities:

```bash
python3 ../skills/security-monitor/scripts/scan_skills.py --paths ./
```

**Do not install them.** These are reference material, not tools.
