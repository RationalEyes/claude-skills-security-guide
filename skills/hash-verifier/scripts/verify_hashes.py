#!/usr/bin/env python3
"""
verify_hashes.py — Claude Skills Integrity Verifier
====================================================
Part of the Claude Skills Injection Defense Suite.

Compares current file hashes against a previously generated manifest
(hashes.json). Reports modifications, new files, and missing files.

Usage:
    python3 verify_hashes.py [--paths PATH...] [--manifest FILE] [--strict]

Exit codes:
    0  All files match the manifest (PASS)
    1  One or more discrepancies found (FAIL)
    2  Manifest does not exist — run generate_manifest.py first
    3  Manifest is malformed or unreadable
    9  Filesystem error
"""

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path


# ---------------------------------------------------------------------------
# Hashing utilities (shared with generate_manifest.py)
# ---------------------------------------------------------------------------

def sha256_file(path: Path) -> str:
    """Compute the SHA-256 hex digest of a file's contents."""
    h = hashlib.sha256()
    try:
        with path.open("rb") as fh:
            for chunk in iter(lambda: fh.read(65536), b""):
                h.update(chunk)
    except OSError as e:
        raise RuntimeError(f"Cannot read {path}: {e}") from e
    return h.hexdigest()


# ---------------------------------------------------------------------------
# Verification logic
# ---------------------------------------------------------------------------

def build_current_hashes(search_paths: list[Path]) -> dict[str, str]:
    """Walk skill directories and compute current hashes, using same key scheme."""
    current: dict[str, str] = {}

    for base in search_paths:
        expanded = Path(os.path.expanduser(str(base)))
        if not expanded.is_dir():
            continue

        base_label = str(expanded)

        for skill_dir in sorted(expanded.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            for file_path in sorted(skill_dir.rglob("*")):
                if not file_path.is_file():
                    continue

                rel = file_path.relative_to(expanded)
                key = base_label + "/" + str(rel).replace("\\", "/")

                try:
                    current[key] = sha256_file(file_path)
                except RuntimeError as e:
                    print(f"  [WARN] {e}", file=sys.stderr)

    return current


def verify(manifest_files: dict[str, str], current_files: dict[str, str]) -> dict:
    """
    Compare manifest vs current state.
    Returns a dict with lists: modified, new_files, missing.
    """
    manifest_keys = set(manifest_files.keys())
    current_keys = set(current_files.keys())

    modified = []
    for key in manifest_keys & current_keys:
        if manifest_files[key] != current_files[key]:
            modified.append({
                "path": key,
                "expected_hash": manifest_files[key],
                "actual_hash": current_files[key],
            })

    new_files = sorted(current_keys - manifest_keys)
    missing = sorted(manifest_keys - current_keys)

    return {
        "modified": sorted(modified, key=lambda x: x["path"]),
        "new_files": new_files,
        "missing": missing,
    }


def render_report(result: dict, manifest_meta: dict) -> str:
    """Render a human-readable verification report."""
    lines = []
    lines.append("=" * 70)
    lines.append("  CLAUDE SKILLS INTEGRITY VERIFICATION REPORT")
    lines.append("=" * 70)
    lines.append(f"  Manifest generated: {manifest_meta.get('generated_at', 'unknown')}")
    lines.append(f"  Files in manifest:  {manifest_meta.get('file_count', '?')}")
    lines.append(f"  Verified at:        {datetime.now(timezone.utc).isoformat()}")
    lines.append("")

    total_issues = (len(result["modified"]) + len(result["new_files"]) +
                    len(result["missing"]))

    if total_issues == 0:
        lines.append("  STATUS: PASS — All files match the manifest.")
        lines.append("=" * 70)
        return "\n".join(lines)

    lines.append(f"  STATUS: FAIL — {total_issues} discrepancy/ies found.")
    lines.append("")

    if result["modified"]:
        lines.append(f"  MODIFIED FILES ({len(result['modified'])}):")
        lines.append("  These files have changed since the manifest was created.")
        lines.append("  This may indicate tampering or an unauthorized update.")
        for entry in result["modified"]:
            lines.append(f"\n    Path: {entry['path']}")
            lines.append(f"    Expected: {entry['expected_hash']}")
            lines.append(f"    Actual:   {entry['actual_hash']}")

    if result["new_files"]:
        lines.append(f"\n  NEW FILES ({len(result['new_files'])}):")
        lines.append("  These files were not present when the manifest was created.")
        lines.append("  Inspect them before trusting any skill in this directory.")
        for path in result["new_files"]:
            lines.append(f"    {path}")

    if result["missing"]:
        lines.append(f"\n  MISSING FILES ({len(result['missing'])}):")
        lines.append("  These files were in the manifest but are no longer on disk.")
        for path in result["missing"]:
            lines.append(f"    {path}")

    lines.append("\n" + "=" * 70)
    lines.append("  ACTION REQUIRED: Do not use flagged skills until discrepancies")
    lines.append("  are investigated. Run generate_manifest.py --force only after")
    lines.append("  you have manually reviewed and approved the current state.")
    lines.append("=" * 70)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Verify Claude Skills file integrity against a stored manifest."
    )
    parser.add_argument(
        "--paths", nargs="+", default=["~/.claude/skills", ".claude/skills"],
        metavar="PATH",
        help="Skill root directories to verify (default: ~/.claude/skills .claude/skills)",
    )
    parser.add_argument(
        "--manifest", default="~/.claude/skill-hashes.json", metavar="FILE",
        help="Path to the manifest JSON (default: ~/.claude/skill-hashes.json)",
    )
    parser.add_argument(
        "--output-json", metavar="FILE",
        help="Write JSON result to FILE in addition to text report",
    )
    parser.add_argument(
        "--strict", action="store_true",
        help="Exit 1 even if only new (unregistered) files are found",
    )
    args = parser.parse_args()

    manifest_path = Path(os.path.expanduser(args.manifest))

    if not manifest_path.exists():
        print(f"Manifest not found: {manifest_path}", file=sys.stderr)
        print("Run generate_manifest.py first to create an initial manifest.", file=sys.stderr)
        sys.exit(2)

    try:
        manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        print(f"Cannot read manifest: {e}", file=sys.stderr)
        sys.exit(3)

    manifest_files: dict[str, str] = manifest_data.get("files", {})
    if not manifest_files:
        print("Manifest is empty or malformed.", file=sys.stderr)
        sys.exit(3)

    search_paths = [Path(p) for p in args.paths]
    current_files = build_current_hashes(search_paths)

    result = verify(manifest_files, current_files)

    # Print text report
    report_text = render_report(result, manifest_data)
    print(report_text)

    # Optionally write JSON result
    if args.output_json:
        try:
            Path(args.output_json).write_text(
                json.dumps(result, indent=2), encoding="utf-8"
            )
            print(f"JSON result written to {args.output_json}")
        except OSError as e:
            print(f"Could not write JSON output: {e}", file=sys.stderr)

    # Exit code
    has_issues = bool(result["modified"] or result["missing"])
    has_new = bool(result["new_files"])

    if has_issues or (args.strict and has_new):
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
