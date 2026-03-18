# Executive Summary: Claude Skills as a Prompt Injection Attack Surface

**Prepared for:** Security Leadership and AI Governance Decision-Makers
**Date:** 2026-03-14
**Classification:** Research / Educational Use

---

## The Risk

Claude Skills — structured instruction files that the Claude AI agent system auto-loads and executes based on pattern matching — are treated by the AI model as system-level trusted instructions. Any user, developer, or attacker can create and install a skill file with no automated review, cryptographic verification, or security gate of any kind. An independent security scan of 3,984 community skill files found that **36.82% contain security flaws** and **13.4% contain critical-severity issues** (Snyk ToxicSkills, February 2026).

## How It Works

When a user installs a skill, a file called `SKILL.md` is placed in a directory on their machine or cloud environment. At the start of every Claude session, the AI reads all installed skills' descriptions and automatically activates relevant ones based on its own language understanding — without prompting the user. Once activated, the skill's full instructions are injected into the AI's reasoning context at the same authority level as Anthropic's own system prompt. Skills can also contain executable scripts that run on the host machine with the full permissions of the logged-in user, and that script output flows back into the AI's reasoning as trusted data — with no sanitization layer between them.

## What Is at Stake

A malicious skill, once installed, can silently exfiltrate credentials and sensitive data, install persistent backdoors that survive system reboots and session resets, and propagate across an entire fleet of AI agents running in the same environment. When organizations use Claude Code's Agent Teams functionality, a single compromised skill can infect all agents sharing the same project directory — creating a worm-like spread pattern with no current containment mechanism. The broader supply chain risk extends to any organization whose developers install skills from community repositories.

## Key Numbers

- **80%** — attack success rate against frontier AI models in the Skill-Inject benchmark (Schmotz et al., arXiv:2602.20156, February 2026)
- **85%+** — attack success rate when adaptive attack strategies are employed against state-of-the-art defenses (SoK paper, arXiv:2601.17548, January 2026)
- **97%** — rate at which a multi-agent AI system executed malicious code when interacting with a compromised local file (Magentic-One research; note: primary source requires additional verification)
- **36.82%** — proportion of 3,984 community skill files containing at least one security flaw (Snyk, February 2026)
- **13.4%** — proportion with critical-severity flaws specifically
- **335+** — malicious skills deployed in the coordinated ClawHavoc campaign (341 total discovered; 824+ confirmed malicious by February 16, 2026)
- **CVE-2025-59536** (CVSS 8.7) and **CVE-2026-21852** (CVSS 5.3) — documented real-world Claude Code exploits via project configuration files, patched post-disclosure
- **89%** — year-over-year increase in AI-enabled cyberattacks (CrowdStrike 2026 Global Threat Report)
- **88%** — organizations reporting a confirmed or suspected AI agent security incident in the past year (CrowdStrike 2026)

## Recommendations

1. **Require cryptographic signing for all skills.** No unsigned skill should load in any production or enterprise environment. The OpenSSF Model Signing (OMS) specification (June 2025) provides a production-ready framework using Sigstore Bundle Format — implementation requires development investment but no new tooling.

2. **Enforce mandatory sandboxing for script execution.** Claude Code's OS-level sandboxing (macOS Seatbelt, Linux bubblewrap) exists but is not enabled by default for skill scripts. Make it mandatory. Add environment variable filtering so skills cannot access `$ANTHROPIC_API_KEY`, `$AWS_SECRET_ACCESS_KEY`, or other sensitive credentials.

3. **Implement static analysis at skill install time.** Scan for known dangerous patterns: `curl`/`wget` in scripts (exfiltration), environment variable access for secrets, cron/persistence installation, overly broad `description` fields that trigger on virtually any input. Reject or quarantine flagged skills pending human review.

4. **Sanitize script output before it enters AI context.** Script stdout should not flow unsanitized into the LLM reasoning context. Apply injection pattern detection, maximum output length limits, and credential-pattern redaction. The CaMeL framework (Google DeepMind, arXiv:2503.18813) provides a proven architecture, achieving 77% task completion with provable security guarantees.

5. **Restrict `allowed-tools` defaults in skill frontmatter.** Skills should not be able to self-declare Bash access without explicit enterprise administrator approval. Human approval should be required for any tool that writes to the filesystem or makes network requests.

6. **Require human review and approval for all third-party skills.** No community skill should auto-install without a security team sign-off. Implement an internal skills allowlist; treat any skill not on the list as untrusted regardless of source.

## Regulatory Context

Organizations using Claude Code with skills in contexts involving financial decisions, sensitive data, or essential services will likely face classification as **high-risk AI systems** under the EU AI Act, triggering mandatory conformity assessment, risk management documentation, and continuous monitoring requirements. The compliance deadline for high-risk AI system operators is **August 2, 2026** — approximately five months from the date of this report. NIST AI RMF (and the NIST Generative AI Profile, AI 600-1) provides a parallel US framework; the NIST 2025 agentic AI initiative specifically addresses systems with planning, tool use, and multi-step action capabilities — exactly the Claude Skills architecture.

---

*This executive summary is part of the Claude Skills Injection: Threat and Defense Guide research project. All findings are for educational and defensive research purposes. See the full technical manual and threat taxonomy for detailed analysis.*
