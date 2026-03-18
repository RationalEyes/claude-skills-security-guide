#!/usr/bin/env python3
"""
generate_manifest.py — Claude Skills Hash Manifest Generator
=============================================================
Part of the Claude Skills Injection Defense Suite.

Creates a JSON manifest of SHA-256 hashes for all files in the specified
skill directories. Run this immediately after reviewing and trusting a set
of skills. The manifest is then used by verify_hashes.py to detect changes.

Usage:
    python3 generate_manifest.py [--paths PATH...] [--manifest FILE] [--force]

Exit codes:
    0  Manifest created or updated successfully
    1  No skill files found
    2  Manifest already exists and --force not specified
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
# Hashing utilities
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
# Skill directory discovery
# ---------------------------------------------------------------------------

def find_skill_files(search_paths: list[Path]) -> dict[str, str]:
    """
    Walk all skill directories under search_paths and return a dict mapping
    relative paths (str) to SHA-256 hex digests.

    Relative paths use forward slashes and are relative to the search_path
    root, e.g. "my-skill/SKILL.md" or "my-skill/scripts/run.py".
    """
    manifest_entries: dict[str, str] = {}

    for base in search_paths:
        expanded = Path(os.path.expanduser(str(base)))
        if not expanded.is_dir():
            print(f"  [SKIP] {expanded} — directory does not exist", file=sys.stderr)
            continue

        base_label = str(expanded)
        print(f"  [SCAN] {base_label}")

        for skill_dir in sorted(expanded.iterdir()):
            if not skill_dir.is_dir() or skill_dir.name.startswith('.'):
                continue

            skill_name = skill_dir.name
            file_count = 0

            for file_path in sorted(skill_dir.rglob("*")):
                if not file_path.is_file():
                    continue

                # Build a stable relative key: base_label/skill/path/to/file
                rel = file_path.relative_to(expanded)
                key = base_label + "/" + str(rel).replace("\\", "/")

                try:
                    digest = sha256_file(file_path)
                    manifest_entries[key] = digest
                    file_count += 1
                except RuntimeError as e:
                    print(f"    [WARN] {e}", file=sys.stderr)

            print(f"    {skill_name}: {file_count} file(s) hashed")

    return manifest_entries


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate a SHA-256 hash manifest for installed Claude Skills."
    )
    parser.add_argument(
        "--paths", nargs="+", default=["~/.claude/skills", ".claude/skills"],
        metavar="PATH",
        help="Skill root directories to scan (default: ~/.claude/skills .claude/skills)",
    )
    parser.add_argument(
        "--manifest", default="~/.claude/skill-hashes.json", metavar="FILE",
        help="Path to write the manifest JSON (default: ~/.claude/skill-hashes.json)",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite an existing manifest without prompting",
    )
    args = parser.parse_args()

    manifest_path = Path(os.path.expanduser(args.manifest))
    search_paths = [Path(p) for p in args.paths]

    # Guard against accidental overwrites
    if manifest_path.exists() and not args.force:
        print(f"Manifest already exists at: {manifest_path}", file=sys.stderr)
        print("Use --force to overwrite it.", file=sys.stderr)
        sys.exit(2)

    print("Generating skill hash manifest...")
    entries = find_skill_files(search_paths)

    if not entries:
        print("No skill files found. Manifest not created.", file=sys.stderr)
        sys.exit(1)

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "generator": "generate_manifest.py v1.0.0",
        "paths_scanned": [str(Path(os.path.expanduser(p))) for p in args.paths],
        "file_count": len(entries),
        "files": entries,
    }

    try:
        manifest_path.parent.mkdir(parents=True, exist_ok=True)
        manifest_path.write_text(
            json.dumps(manifest, indent=2, sort_keys=True),
            encoding="utf-8",
        )
    except OSError as e:
        print(f"Failed to write manifest: {e}", file=sys.stderr)
        sys.exit(9)

    print(f"\nManifest written to: {manifest_path}")
    print(f"Files recorded: {len(entries)}")
    print("\nIMPORTANT: Store this manifest in a trusted, version-controlled")
    print("location. It is only as trustworthy as the moment it was generated.")
    print("Run verify_hashes.py before each session to detect subsequent changes.")


if __name__ == "__main__":
    main()
