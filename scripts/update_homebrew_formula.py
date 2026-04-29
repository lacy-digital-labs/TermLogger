#!/usr/bin/env python3
"""Update the Homebrew formula with a new version and SHA256 hashes.

Usage:
    python3 scripts/update_homebrew_formula.py <formula_path> <version> <arm64_sha> <x86_64_sha>

Example:
    python3 scripts/update_homebrew_formula.py ../homebrew-termlogger/Formula/termlogger.rb \\
        26.01.03 abc123... def456...
"""

import re
import sys
from pathlib import Path


def update_formula(formula_path: str, version: str, arm64_sha: str, x86_64_sha: str) -> None:
    path = Path(formula_path)
    text = path.read_text()

    text = re.sub(r'version "[^"]+"', f'version "{version}"', text)

    lines = text.splitlines(keepends=True)
    result = []
    sha_index = 0  # 0 = arm64, 1 = x86_64
    for line in lines:
        if re.search(r'sha256 "(?:PLACEHOLDER_[A-Z0-9_]+|[a-f0-9]{64})"', line):
            sha = arm64_sha if sha_index == 0 else x86_64_sha
            line = re.sub(r'"(?:PLACEHOLDER_[A-Z0-9_]+|[a-f0-9]{64})"', f'"{sha}"', line)
            sha_index += 1
        result.append(line)

    path.write_text("".join(result))
    print(f"Updated {formula_path} to version {version}")


if __name__ == "__main__":
    if len(sys.argv) != 5:
        print(__doc__)
        sys.exit(1)
    update_formula(sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4])
