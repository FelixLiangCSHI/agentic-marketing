#!/usr/bin/env python3
"""Secret scan gate for plain PR CI.

Scans git-tracked files for credential-looking content. Exits non-zero on any
finding so the CI job fails closed. Allowed forms: ``secretref://provider/path``
references and clearly synthetic local-dev values listed in ALLOWLIST.

Usage: python3 scripts/check_no_secrets.py [path ...]
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("private-key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |PGP )?PRIVATE KEY-----")),
    ("aws-access-key-id", re.compile(r"\b(?:AKIA|ASIA)[0-9A-Z]{16}\b")),
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{36,}\b")),
    ("slack-token", re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b")),
    ("openai-style-key", re.compile(r"\bsk-[A-Za-z0-9]{20,}\b")),
    ("google-api-key", re.compile(r"\bAIza[0-9A-Za-z_-]{35}\b")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "url-with-password",
        re.compile(r"\b[a-z][a-z0-9+.-]*://[^/\s:@]+:[^/\s:@]+@[^\s]+"),
    ),
    (
        "hardcoded-credential-assignment",
        re.compile(
            r"(?i)\b(api[_-]?key|secret[_-]?key|client[_-]?secret|access[_-]?token|password)\b"
            r"\s*[:=]\s*['\"](?!secretref://)[A-Za-z0-9+/_-]{16,}['\"]"
        ),
    ),
]

SKIP_SUFFIXES = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".pdf", ".woff", ".woff2", ".xlsx"}
SKIP_PATHS = {"package-lock.json", "scripts/check_no_secrets.py"}

# Well-known synthetic local-dev values; never real credentials.
ALLOWLIST = {"minioadmin"}


def tracked_files(root: Path) -> list[Path]:
    output = subprocess.run(
        ["git", "ls-files", "-z"], cwd=root, check=True, capture_output=True, text=True
    ).stdout
    return [root / name for name in output.split("\0") if name]


def scan_file(path: Path, root: Path) -> list[str]:
    relative = path.relative_to(root).as_posix() if path.is_relative_to(root) else str(path)
    if relative in SKIP_PATHS or path.suffix in SKIP_SUFFIXES:
        return []
    try:
        text = path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return []
    findings = []
    for line_number, line in enumerate(text.splitlines(), start=1):
        for name, pattern in PATTERNS:
            match = pattern.search(line)
            if match and match.group(0) not in ALLOWLIST:
                findings.append(f"{relative}:{line_number}: {name}")
    return findings


def main(argv: list[str]) -> int:
    root = Path(
        subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()
    )
    targets = [Path(arg).resolve() for arg in argv] or tracked_files(root)
    findings: list[str] = []
    for path in targets:
        if path.is_file():
            findings.extend(scan_file(path, root))
    if findings:
        print("SECRET SCAN FAILED — potential credentials found:", file=sys.stderr)
        for finding in findings:
            print(f"  {finding}", file=sys.stderr)
        return 1
    print(f"secret scan clean ({len(targets)} files)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
