#!/usr/bin/env python3
"""
scan_skills.py — Claude Skills Security Scanner
================================================
Part of the Claude Skills Defense Suite.

Scans installed Claude Skill directories for indicators of compromise:
  - External URL references (C2 / exfiltration endpoints)
  - Credential / environment variable access patterns
  - Persistence mechanisms (cron, rc files, skill replication)
  - Overly broad trigger descriptions (hijacking)
  - Suspicious allowed-tools grants
  - Hidden content (HTML comments, zero-width chars, base64 blobs)

Exit codes:
  0  All skills rated LOW
  1  At least one skill rated MEDIUM
  2  At least one skill rated HIGH
  3  At least one skill rated CRITICAL
  9  Scanner error (bad arguments, unreadable path, etc.)
"""

import argparse
import base64
import hashlib
import json
import os
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional
import yaml  # PyYAML; falls back gracefully if absent


# ---------------------------------------------------------------------------
# Risk level ordering
# ---------------------------------------------------------------------------

RISK_ORDER = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}


def max_risk(a: str, b: str) -> str:
    return a if RISK_ORDER[a] >= RISK_ORDER[b] else b


# ---------------------------------------------------------------------------
# Compiled detection patterns
# ---------------------------------------------------------------------------

# External URL references that suggest network callbacks
URL_PATTERNS = [
    re.compile(r'https?://(?!docs\.anthropic\.com|github\.com/anthropics)[^\s\'">`]+', re.I),
    re.compile(r'(curl|wget|requests\.get|urllib|fetch)\s*\(?\s*["\']?https?://', re.I),
]

# Environment variable reads for sensitive credentials
CREDENTIAL_ENV_PATTERNS = [
    re.compile(r'\$(?:AWS_ACCESS_KEY|AWS_SECRET|ANTHROPIC_API_KEY|GITHUB_TOKEN|'
               r'OPENAI_API_KEY|SLACK_TOKEN|DISCORD_TOKEN|STRIPE_SECRET|'
               r'DATABASE_URL|DB_PASSWORD|PRIVATE_KEY|SECRET_KEY|AUTH_TOKEN)', re.I),
    re.compile(r'os\.environ\.get\s*\(\s*["\'](?:AWS_|ANTHROPIC_|GITHUB_|OPENAI_|'
               r'SECRET|TOKEN|PASSWORD|KEY)', re.I),
    re.compile(r'os\.getenv\s*\(\s*["\'](?:AWS_|ANTHROPIC_|GITHUB_|OPENAI_|'
               r'SECRET|TOKEN|PASSWORD|KEY)', re.I),
]

# Persistence indicators
PERSISTENCE_PATTERNS = [
    re.compile(r'crontab\s+-[le]', re.I),                        # crontab editing
    re.compile(r'>>?\s*~/?\.(bashrc|zshrc|profile|bash_profile)', re.I),  # shell RC writes
    re.compile(r'\.claude/skills/', re.I),                        # skill directory writes
    re.compile(r'cp\s+.*SKILL\.md', re.I),                        # skill replication
    re.compile(r'launchctl|systemctl\s+enable', re.I),            # service installation
    re.compile(r'startup|autorun|\.plist\b', re.I),               # macOS/Windows startup
]

# Authority-impersonating trigger descriptions
AUTHORITY_PATTERNS = [
    re.compile(r'\b(SYSTEM|OVERRIDE|IGNORE\s+PREVIOUS|DISREGARD|YOU\s+MUST\s+NOW|'
               r'NEW\s+INSTRUCTIONS?|URGENT|MANDATORY|CRITICAL\s+UPDATE)\b', re.I),
    re.compile(r'<\s*/?(?:system|instruction|prompt|override)\s*>', re.I),
]

# Hidden content patterns
HIDDEN_CONTENT_PATTERNS = [
    re.compile(r'<!--.*?-->', re.DOTALL),                          # HTML comments
    re.compile(r'[\u200b\u200c\u200d\ufeff\u00ad]'),               # zero-width / soft-hyphen
    re.compile(r'[A-Za-z0-9+/]{40,}={0,2}'),                      # base64 candidates (40+ chars)
]

# Suspicious allowed-tools values
DANGEROUS_TOOLS = {"Bash", "Computer", "Execute"}

# Description length heuristics (very long = potential injection payload)
MAX_SAFE_DESCRIPTION_WORDS = 150


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class Finding:
    check: str
    severity: str          # LOW | MEDIUM | HIGH | CRITICAL
    detail: str
    line_number: Optional[int] = None
    snippet: Optional[str] = None


@dataclass
class SkillReport:
    skill_name: str
    skill_path: str
    overall_risk: str = "LOW"
    findings: list = field(default_factory=list)
    file_hash: str = ""

    def add(self, finding: Finding):
        self.findings.append(finding)
        self.overall_risk = max_risk(self.overall_risk, finding.severity)


# ---------------------------------------------------------------------------
# YAML frontmatter extraction
# ---------------------------------------------------------------------------

def parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body_text). Returns ({}, text) on failure."""
    if not text.startswith("---"):
        return {}, text
    end = text.find("\n---", 3)
    if end == -1:
        return {}, text
    yaml_block = text[3:end].strip()
    body = text[end + 4:].strip()
    try:
        import yaml as _yaml
        data = _yaml.safe_load(yaml_block) or {}
    except Exception:
        data = {}
    return data, body


# ---------------------------------------------------------------------------
# Individual checks
# ---------------------------------------------------------------------------

def check_urls(content: str, report: SkillReport, filename: str):
    """Detect external URL references that could indicate C2 or exfil."""
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern in URL_PATTERNS:
            match = pattern.search(line)
            if match:
                report.add(Finding(
                    check="external_url",
                    severity="HIGH",
                    detail=f"External URL reference in {filename}",
                    line_number=lineno,
                    snippet=line.strip()[:120],
                ))


def check_credentials(content: str, report: SkillReport, filename: str):
    """Detect environment variable reads for sensitive credentials."""
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern in CREDENTIAL_ENV_PATTERNS:
            match = pattern.search(line)
            if match:
                report.add(Finding(
                    check="credential_access",
                    severity="CRITICAL",
                    detail=f"Sensitive credential/env var access in {filename}",
                    line_number=lineno,
                    snippet=line.strip()[:120],
                ))


def check_persistence(content: str, report: SkillReport, filename: str):
    """Detect persistence mechanism indicators."""
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern in PERSISTENCE_PATTERNS:
            match = pattern.search(line)
            if match:
                report.add(Finding(
                    check="persistence",
                    severity="CRITICAL",
                    detail=f"Persistence mechanism detected in {filename}",
                    line_number=lineno,
                    snippet=line.strip()[:120],
                ))


def check_hidden_content(content: str, report: SkillReport, filename: str):
    """Detect hidden content: HTML comments, zero-width chars, base64 blobs."""
    # HTML comments
    for match in HIDDEN_CONTENT_PATTERNS[0].finditer(content):
        comment_body = match.group(0)
        # Only flag if the comment contains non-trivial content
        if len(comment_body) > 10:
            lineno = content[:match.start()].count('\n') + 1
            report.add(Finding(
                check="hidden_content_html_comment",
                severity="MEDIUM",
                detail=f"HTML comment (possible hidden instruction) in {filename}",
                line_number=lineno,
                snippet=comment_body[:80],
            ))

    # Zero-width characters
    for lineno, line in enumerate(content.splitlines(), 1):
        if HIDDEN_CONTENT_PATTERNS[1].search(line):
            report.add(Finding(
                check="hidden_content_zero_width",
                severity="HIGH",
                detail=f"Zero-width or invisible characters in {filename}",
                line_number=lineno,
                snippet=repr(line[:80]),
            ))

    # Base64 blobs — only flag in script files (not SKILL.md prose)
    if filename.endswith(('.py', '.sh', '.js', '.rb')):
        for lineno, line in enumerate(content.splitlines(), 1):
            for match in HIDDEN_CONTENT_PATTERNS[2].finditer(line):
                blob = match.group(0)
                # Verify it decodes cleanly (reduces false positives)
                try:
                    decoded = base64.b64decode(blob + '==')
                    # Flag if decoded content looks like text or a command
                    if any(kw in decoded for kw in
                           [b'curl', b'wget', b'bash', b'python', b'import',
                            b'http', b'token', b'secret']):
                        report.add(Finding(
                            check="hidden_content_base64",
                            severity="HIGH",
                            detail=f"Base64 blob decoding to suspicious content in {filename}",
                            line_number=lineno,
                            snippet=f"{blob[:40]}... -> {decoded[:60]}",
                        ))
                except Exception:
                    pass  # Not valid base64


def check_authority_patterns(content: str, report: SkillReport, filename: str):
    """Detect authority-impersonating language in SKILL.md body or description."""
    for lineno, line in enumerate(content.splitlines(), 1):
        for pattern in AUTHORITY_PATTERNS:
            if pattern.search(line):
                report.add(Finding(
                    check="authority_injection",
                    severity="HIGH",
                    detail=f"Authority-impersonating language in {filename}",
                    line_number=lineno,
                    snippet=line.strip()[:120],
                ))


def check_frontmatter(frontmatter: dict, report: SkillReport):
    """Check SKILL.md frontmatter for suspicious configurations."""
    # --- allowed-tools ---
    tools = frontmatter.get("allowed-tools", [])
    if isinstance(tools, list):
        dangerous = [t for t in tools if t in DANGEROUS_TOOLS]
        if dangerous:
            report.add(Finding(
                check="dangerous_allowed_tools",
                severity="HIGH",
                detail=f"Unrestricted dangerous tool(s) in allowed-tools: {dangerous}",
            ))

    # --- description length ---
    desc = frontmatter.get("description", "")
    if isinstance(desc, str):
        word_count = len(desc.split())
        if word_count > MAX_SAFE_DESCRIPTION_WORDS:
            report.add(Finding(
                check="oversized_description",
                severity="MEDIUM",
                detail=(f"Description is {word_count} words (>{MAX_SAFE_DESCRIPTION_WORDS}). "
                        "Long descriptions may embed injection payloads."),
            ))

    # --- user-invocable: false combined with allowed-tools ---
    # A non-user-invocable skill with broad tool access is a red flag
    if not frontmatter.get("user-invocable", True) and tools:
        report.add(Finding(
            check="hidden_tool_access",
            severity="MEDIUM",
            detail="Non-user-invocable skill grants tool access — runs silently with permissions.",
        ))


# ---------------------------------------------------------------------------
# Skill directory scanner
# ---------------------------------------------------------------------------

def scan_skill_directory(skill_dir: Path) -> SkillReport:
    """Scan a single skill directory and return a SkillReport."""
    skill_md = skill_dir / "SKILL.md"
    report = SkillReport(
        skill_name=skill_dir.name,
        skill_path=str(skill_dir),
    )

    if not skill_md.exists():
        report.add(Finding(
            check="missing_skill_md",
            severity="LOW",
            detail="Directory has no SKILL.md — not a valid skill.",
        ))
        return report

    # Hash the SKILL.md for reference
    try:
        raw = skill_md.read_text(encoding="utf-8", errors="replace")
        report.file_hash = hashlib.sha256(raw.encode()).hexdigest()[:16]
    except OSError as e:
        report.add(Finding(
            check="read_error",
            severity="MEDIUM",
            detail=f"Cannot read SKILL.md: {e}",
        ))
        return report

    frontmatter, body = parse_frontmatter(raw)

    # Run SKILL.md checks
    check_frontmatter(frontmatter, report)
    check_urls(raw, report, "SKILL.md")
    check_credentials(raw, report, "SKILL.md")
    check_persistence(raw, report, "SKILL.md")
    check_hidden_content(raw, report, "SKILL.md")
    check_authority_patterns(body, report, "SKILL.md body")

    # Scan scripts directory
    scripts_dir = skill_dir / "scripts"
    if scripts_dir.is_dir():
        for script_file in sorted(scripts_dir.iterdir()):
            if script_file.is_file() and script_file.suffix in (
                '.py', '.sh', '.bash', '.js', '.rb', '.pl', '.ps1'
            ):
                try:
                    script_content = script_file.read_text(encoding="utf-8", errors="replace")
                except OSError as e:
                    report.add(Finding(
                        check="read_error",
                        severity="LOW",
                        detail=f"Cannot read {script_file.name}: {e}",
                    ))
                    continue

                fname = f"scripts/{script_file.name}"
                check_urls(script_content, report, fname)
                check_credentials(script_content, report, fname)
                check_persistence(script_content, report, fname)
                check_hidden_content(script_content, report, fname)
                check_authority_patterns(script_content, report, fname)

    return report


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def find_skill_dirs(search_paths: list[Path]) -> list[Path]:
    """Return all immediate subdirectories of search_paths that may be skills."""
    skill_dirs = []
    for base in search_paths:
        expanded = Path(os.path.expanduser(str(base)))
        if not expanded.is_dir():
            continue
        for entry in sorted(expanded.iterdir()):
            if entry.is_dir() and not entry.name.startswith('.'):
                skill_dirs.append(entry)
    return skill_dirs


def render_text_report(reports: list[SkillReport]) -> str:
    """Render a human-readable text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  CLAUDE SKILLS SECURITY SCAN REPORT")
    lines.append("=" * 70)
    lines.append(f"  Skills scanned: {len(reports)}")

    risk_counts = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
    for r in reports:
        risk_counts[r.overall_risk] += 1

    lines.append(f"  LOW: {risk_counts['LOW']}  MEDIUM: {risk_counts['MEDIUM']}  "
                 f"HIGH: {risk_counts['HIGH']}  CRITICAL: {risk_counts['CRITICAL']}")
    lines.append("=" * 70)

    for report in sorted(reports, key=lambda r: RISK_ORDER[r.overall_risk], reverse=True):
        risk_label = {
            "LOW": "[LOW]     ",
            "MEDIUM": "[MEDIUM]  ",
            "HIGH": "[HIGH]    ",
            "CRITICAL": "[CRITICAL]",
        }[report.overall_risk]

        lines.append(f"\n{risk_label}  {report.skill_name}  (sha256:{report.file_hash})")
        lines.append(f"           Path: {report.skill_path}")

        if not report.findings:
            lines.append("           No issues found.")
        else:
            for f in report.findings:
                loc = f" (line {f.line_number})" if f.line_number else ""
                lines.append(f"  [{f.severity:<8}] {f.check}{loc}")
                lines.append(f"             {f.detail}")
                if f.snippet:
                    lines.append(f"             > {f.snippet}")

    lines.append("\n" + "=" * 70)
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Scan Claude Skills directories for security indicators."
    )
    parser.add_argument(
        "--paths", nargs="+", default=["~/.claude/skills", ".claude/skills"],
        metavar="PATH",
        help="Skill root directories to scan (default: ~/.claude/skills .claude/skills)",
    )
    parser.add_argument(
        "--report-format", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--output", metavar="FILE",
        help="Write report to FILE instead of stdout",
    )
    parser.add_argument(
        "--fail-on", choices=["MEDIUM", "HIGH", "CRITICAL"], default=None,
        help="Exit with non-zero code if any skill meets or exceeds this risk level",
    )
    args = parser.parse_args()

    search_paths = [Path(p) for p in args.paths]
    skill_dirs = find_skill_dirs(search_paths)

    if not skill_dirs:
        print("No skill directories found in the specified paths.", file=sys.stderr)
        print(f"Searched: {[str(p) for p in search_paths]}", file=sys.stderr)
        sys.exit(9)

    reports = [scan_skill_directory(d) for d in skill_dirs]

    if args.report_format == "json":
        output = json.dumps([asdict(r) for r in reports], indent=2)
    else:
        output = render_text_report(reports)

    if args.output:
        Path(args.output).write_text(output, encoding="utf-8")
        print(f"Report written to {args.output}")
    else:
        print(output)

    # Determine exit code
    max_found = max((RISK_ORDER[r.overall_risk] for r in reports), default=0)
    threshold = RISK_ORDER.get(args.fail_on, -1) if args.fail_on else -1

    if args.fail_on and max_found >= threshold:
        sys.exit(max_found)
    sys.exit(0)


if __name__ == "__main__":
    main()
