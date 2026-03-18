#!/usr/bin/env python3
"""
sanitize_output.py — Claude Skills Output Sanitizer
====================================================
Part of the Claude Skills Injection Defense Suite.

Validates and sanitizes text content to prevent second-order prompt injection
attacks before the content enters Claude's context window as interpreted input.

Checks performed:
  1. Instruction-like patterns (IMPORTANT, SYSTEM, IGNORE PREVIOUS, etc.)
  2. XML/HTML tag injection (especially system/instruction tags)
  3. Credential-like patterns (API keys, tokens, passwords)
  4. Output length enforcement
  5. Base64-encoded payload detection
  6. Null-byte and control-character injection

Usage:
    python3 sanitize_output.py [OPTIONS] [FILE]
    echo "content" | python3 sanitize_output.py [OPTIONS]

Exit codes:
    0  Content is clean or was sanitized with only LOW findings
    1  MEDIUM findings detected (content was modified)
    2  HIGH findings detected (content contains injection attempts)
    3  CRITICAL findings detected (credential exposure, severe injection)
    9  Usage or I/O error
"""

import argparse
import base64
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from typing import Optional


# ---------------------------------------------------------------------------
# Configuration defaults
# ---------------------------------------------------------------------------

DEFAULT_MAX_LENGTH = 50_000       # characters
DEFAULT_MAX_LINE_LENGTH = 2_000   # characters per line
CREDENTIAL_REPLACEMENT = "[REDACTED]"
INJECTION_REPLACEMENT = "[SANITIZED]"


# ---------------------------------------------------------------------------
# Detection patterns
# ---------------------------------------------------------------------------

# Instruction-injection keywords and phrases commonly used in prompt injections
# These are phrases that only make sense as instructions, not as data
INSTRUCTION_PATTERNS = [
    # Direct override language
    (re.compile(
        r'\b(IGNORE\s+(PREVIOUS|ALL|ABOVE|PRIOR)\s+(INSTRUCTIONS?|CONTEXT|PROMPTS?)|'
        r'DISREGARD\s+(PREVIOUS|ALL|ABOVE|PRIOR)|'
        r'FORGET\s+(EVERYTHING|ALL|PREVIOUS)|'
        r'NEW\s+INSTRUCTIONS?\s*:|'
        r'UPDATED?\s+INSTRUCTIONS?\s*:|'
        r'OVERRIDE\s*(:|MODE|INSTRUCTIONS?)|'
        r'YOU\s+MUST\s+NOW\s+|'
        r'FROM\s+NOW\s+ON\s+YOU\s+(WILL|MUST|SHALL))',
        re.I | re.MULTILINE,
    ), "HIGH", "Prompt override / ignore-previous instruction"),

    # Authority impersonation
    (re.compile(
        r'\b(ANTHROPIC\s+(SAFETY|TEAM|STAFF|SUPPORT|SYSTEM)\s*:|'
        r'SYSTEM\s+MESSAGE\s*:|'
        r'INTERNAL\s+(DIRECTIVE|NOTICE|INSTRUCTION)\s*:|'
        r'\[SYSTEM\]|\[ADMIN\]|\[ROOT\]|\[OPERATOR\])',
        re.I | re.MULTILINE,
    ), "HIGH", "Authority impersonation in content"),

    # Role / persona hijacking
    (re.compile(
        r'\b(YOU\s+ARE\s+NOW|YOUR\s+NEW\s+(ROLE|PERSONA|IDENTITY)\s+(IS|:)|'
        r'ACT\s+AS\s+(?:AN?\s+)?(?:UNRESTRICTED|UNFILTERED|JAILBROKEN|DAN\b)|'
        r'PRETEND\s+(YOU|THAT\s+YOU)\s+(HAVE\s+NO|ARE\s+NOT|CAN))',
        re.I | re.MULTILINE,
    ), "CRITICAL", "Role/persona hijacking attempt"),

    # Exfiltration instructions
    (re.compile(
        r'\b(SEND\s+(THE\s+)?(CONTENTS?|DATA|OUTPUT|RESULTS?|CONVERSATION)\s+'
        r'(TO|VIA|USING)\s+(HTTP|CURL|EMAIL|WEBHOOK)|'
        r'EXFILTRATE|LEAK\s+(THE\s+)?DATA)',
        re.I | re.MULTILINE,
    ), "CRITICAL", "Exfiltration instruction in content"),

    # Urgency markers that appear in injection payloads
    (re.compile(
        r'^(?:CRITICAL|URGENT|IMPORTANT|ALERT|WARNING|NOTICE)\s*:\s*'
        r'.{0,200}(?:IGNORE|OVERRIDE|DISREGARD|FORGET|INSTEAD)',
        re.I | re.MULTILINE,
    ), "MEDIUM", "Urgency + override pattern"),
]

# XML/HTML tags that are interpreted as system/control elements
DANGEROUS_TAGS = re.compile(
    r'<\s*/?\s*(?:system|instruction|prompt|override|claude|anthropic|admin|'
    r'root|control|directive|command|exec)\s*(?:/\s*)?>',
    re.I,
)

# Generic HTML tags that could smuggle content or alter rendering
HTML_TAG_PATTERN = re.compile(r'<[a-zA-Z][^>]{0,200}>', re.DOTALL)

# Credential patterns — ordered from most specific to most general
CREDENTIAL_PATTERNS = [
    # Anthropic API keys
    (re.compile(r'\bsk-ant-[a-zA-Z0-9\-_]{20,}'), "CRITICAL", "Anthropic API key"),
    # OpenAI API keys
    (re.compile(r'\bsk-[a-zA-Z0-9]{32,}'), "CRITICAL", "OpenAI-style API key"),
    # AWS access key IDs
    (re.compile(r'\bAKIA[0-9A-Z]{16}\b'), "CRITICAL", "AWS Access Key ID"),
    # AWS secret keys (heuristic: 40-char mixed alphanumeric after 'aws' context)
    (re.compile(r'(?:aws[_\-]?secret|secret[_\-]?access[_\-]?key)\s*[=:]\s*["\']?[A-Za-z0-9+/]{40}'), "CRITICAL", "AWS Secret Key"),
    # GitHub PATs (classic)
    (re.compile(r'\bghp_[a-zA-Z0-9]{36}\b'), "CRITICAL", "GitHub Personal Access Token"),
    # GitHub fine-grained PATs
    (re.compile(r'\bgithub_pat_[a-zA-Z0-9_]{22,}'), "CRITICAL", "GitHub Fine-grained PAT"),
    # Generic bearer/API tokens in HTTP headers
    (re.compile(r'(?:Authorization|Bearer|X-Api-Key|Api-Token)\s*:\s*[^\s\r\n]{16,}', re.I), "HIGH", "HTTP auth token in content"),
    # Password assignments
    (re.compile(r'(?:password|passwd|pwd)\s*[=:]\s*["\']?[^\s"\']{8,}', re.I), "HIGH", "Plaintext password"),
    # Private key header
    (re.compile(r'-----BEGIN\s+(?:RSA\s+|EC\s+|OPENSSH\s+)?PRIVATE\s+KEY-----'), "CRITICAL", "PEM private key"),
]

# Base64 blob detection (40+ char base64 that decodes to interesting content)
BASE64_BLOB = re.compile(r'(?<![A-Za-z0-9+/])[A-Za-z0-9+/]{40,}={0,2}(?![A-Za-z0-9+/])')

# Suspicious keywords to look for in decoded base64
BASE64_SUSPICIOUS_KEYWORDS = [
    b'curl', b'wget', b'bash', b'python', b'/bin/', b'http://', b'https://',
    b'import os', b'subprocess', b'eval(', b'exec(', b'token', b'secret',
    b'password', b'credential', b'exfil',
]

# Control characters that should not appear in normal text output
CONTROL_CHAR_PATTERN = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class SanitizerWarning:
    check: str
    severity: str        # LOW | MEDIUM | HIGH | CRITICAL
    description: str
    location: Optional[str] = None  # e.g., "line 42" or "character 1500-1540"
    original_snippet: Optional[str] = None


@dataclass
class SanitizerResult:
    original_length: int
    sanitized_length: int
    warnings: list = field(default_factory=list)
    sanitized_text: str = ""
    overall_severity: str = "LOW"

    def add_warning(self, warning: SanitizerWarning):
        self.warnings.append(warning)
        severity_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        if severity_order[warning.severity] > severity_order[self.overall_severity]:
            self.overall_severity = warning.severity


# ---------------------------------------------------------------------------
# Sanitization functions
# ---------------------------------------------------------------------------

def check_length(text: str, result: SanitizerResult, max_length: int) -> str:
    """Enforce maximum content length."""
    if len(text) > max_length:
        result.add_warning(SanitizerWarning(
            check="max_length_exceeded",
            severity="MEDIUM",
            description=(f"Content truncated from {len(text)} to {max_length} characters. "
                         "Unusually long output may be attempting to overwhelm context limits."),
        ))
        return text[:max_length] + f"\n[... TRUNCATED: {len(text) - max_length} characters removed ...]"
    return text


def check_line_lengths(text: str, result: SanitizerResult, max_line: int) -> str:
    """Truncate individual lines that exceed the maximum line length."""
    lines = text.splitlines(keepends=True)
    modified = False
    output_lines = []
    for i, line in enumerate(lines, 1):
        if len(line) > max_line:
            result.add_warning(SanitizerWarning(
                check="line_too_long",
                severity="LOW",
                description=f"Line {i} truncated ({len(line)} > {max_line} chars).",
                location=f"line {i}",
            ))
            line = line[:max_line] + "[TRUNCATED]\n"
            modified = True
        output_lines.append(line)
    return "".join(output_lines)


def strip_control_chars(text: str, result: SanitizerResult) -> str:
    """Remove non-printable control characters."""
    cleaned = CONTROL_CHAR_PATTERN.sub('', text)
    if cleaned != text:
        result.add_warning(SanitizerWarning(
            check="control_characters",
            severity="HIGH",
            description="Non-printable control characters removed. These can hide injected content.",
        ))
    return cleaned


def sanitize_dangerous_tags(text: str, result: SanitizerResult) -> str:
    """Remove XML tags that Claude may interpret as system-level control."""
    def replace_tag(m):
        result.add_warning(SanitizerWarning(
            check="dangerous_xml_tag",
            severity="HIGH",
            description=f"Dangerous XML/control tag removed: {m.group(0)[:60]}",
            original_snippet=m.group(0)[:80],
        ))
        return INJECTION_REPLACEMENT

    return DANGEROUS_TAGS.sub(replace_tag, text)


def sanitize_html_tags(text: str, result: SanitizerResult) -> str:
    """Strip generic HTML tags that could alter LLM rendering or inject content."""
    def replace_html(m):
        tag = m.group(0)
        # Only warn once per unique tag type to avoid warning spam
        return ""  # Strip silently; dangerous tags were already caught above

    cleaned = HTML_TAG_PATTERN.sub(replace_html, text)
    if cleaned != text:
        result.add_warning(SanitizerWarning(
            check="html_tags_stripped",
            severity="LOW",
            description="HTML tags stripped from content to prevent rendering injection.",
        ))
    return cleaned


def detect_instruction_patterns(text: str, result: SanitizerResult) -> str:
    """Detect and redact instruction-injection language."""
    current = text
    for pattern, severity, description in INSTRUCTION_PATTERNS:
        def replace_instruction(m, _desc=description, _sev=severity):
            lineno = text[:m.start()].count('\n') + 1
            result.add_warning(SanitizerWarning(
                check="instruction_injection",
                severity=_sev,
                description=_desc,
                location=f"line {lineno}",
                original_snippet=m.group(0)[:100],
            ))
            return INJECTION_REPLACEMENT

        current = pattern.sub(replace_instruction, current)
    return current


def redact_credentials(text: str, result: SanitizerResult) -> str:
    """Redact credential-like patterns to prevent accidental exposure."""
    current = text
    for pattern, severity, cred_type in CREDENTIAL_PATTERNS:
        def replace_cred(m, _type=cred_type, _sev=severity):
            lineno = text[:m.start()].count('\n') + 1
            result.add_warning(SanitizerWarning(
                check="credential_redacted",
                severity=_sev,
                description=f"{_type} detected and redacted.",
                location=f"line {lineno}",
                original_snippet=f"{m.group(0)[:8]}...[{len(m.group(0))} chars]",
            ))
            return CREDENTIAL_REPLACEMENT

        current = pattern.sub(replace_cred, current)
    return current


def check_base64_blobs(text: str, result: SanitizerResult) -> str:
    """Flag base64 blobs that decode to suspicious content."""
    for match in BASE64_BLOB.finditer(text):
        blob = match.group(0)
        try:
            decoded = base64.b64decode(blob + '==')
            for keyword in BASE64_SUSPICIOUS_KEYWORDS:
                if keyword in decoded.lower():
                    lineno = text[:match.start()].count('\n') + 1
                    result.add_warning(SanitizerWarning(
                        check="suspicious_base64",
                        severity="HIGH",
                        description=(f"Base64 blob decodes to content containing "
                                     f"suspicious keyword '{keyword.decode()}'. "
                                     "This may be an encoded command payload."),
                        location=f"line {lineno}",
                        original_snippet=f"{blob[:40]}...",
                    ))
                    break  # One warning per blob
        except Exception:
            pass  # Not valid base64 — skip
    return text  # We flag but do not remove base64 (too many false positives)


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_text_output(result: SanitizerResult) -> str:
    """Render sanitized output in the format expected by the SKILL.md."""
    lines = []
    lines.append("=== SECURITY WARNINGS ===")

    if not result.warnings:
        lines.append("None detected.")
    else:
        for w in result.warnings:
            loc = f" ({w.location})" if w.location else ""
            lines.append(f"[{w.severity}] {w.check}{loc}: {w.description}")
            if w.original_snippet:
                lines.append(f"       Original: {w.original_snippet}")

    lines.append("")
    lines.append("=== SANITIZED OUTPUT ===")
    lines.append(result.sanitized_text)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

def sanitize(text: str, max_length: int, max_line_length: int) -> SanitizerResult:
    """Run the full sanitization pipeline and return a SanitizerResult."""
    result = SanitizerResult(original_length=len(text), sanitized_length=0)

    # Apply transformations in order (most destructive checks first)
    text = check_length(text, result, max_length)
    text = strip_control_chars(text, result)
    text = sanitize_dangerous_tags(text, result)
    text = sanitize_html_tags(text, result)

    # Detection passes (modify content)
    text = detect_instruction_patterns(text, result)
    text = redact_credentials(text, result)

    # Detection-only passes (flag but preserve)
    check_base64_blobs(text, result)

    # Line-level cleanup
    text = check_line_lengths(text, result, max_line_length)

    result.sanitized_text = text
    result.sanitized_length = len(text)
    return result


def main():
    parser = argparse.ArgumentParser(
        description="Sanitize script output to prevent second-order prompt injection."
    )
    parser.add_argument(
        "file", nargs="?", default="-",
        help="Input file to sanitize (default: stdin)",
    )
    parser.add_argument(
        "--max-length", type=int, default=DEFAULT_MAX_LENGTH,
        help=f"Maximum content length in characters (default: {DEFAULT_MAX_LENGTH})",
    )
    parser.add_argument(
        "--max-line-length", type=int, default=DEFAULT_MAX_LINE_LENGTH,
        help=f"Maximum line length in characters (default: {DEFAULT_MAX_LINE_LENGTH})",
    )
    parser.add_argument(
        "--output-format", choices=["text", "json"], default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--no-html-strip", action="store_true",
        help="Disable HTML tag stripping (for content where HTML is expected)",
    )
    args = parser.parse_args()

    # Read input
    try:
        if args.file == "-":
            text = sys.stdin.read()
        else:
            with open(args.file, encoding="utf-8", errors="replace") as fh:
                text = fh.read()
    except OSError as e:
        print(f"Cannot read input: {e}", file=sys.stderr)
        sys.exit(9)

    result = sanitize(text, args.max_length, args.max_line_length)

    if args.output_format == "json":
        print(json.dumps(asdict(result), indent=2))
    else:
        print(render_text_output(result))

    # Exit code based on severity
    severity_exit = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
    sys.exit(severity_exit[result.overall_severity])


if __name__ == "__main__":
    main()
