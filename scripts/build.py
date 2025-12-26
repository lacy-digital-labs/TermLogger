#!/usr/bin/env python3
"""
Build script for TermLogger.

Creates standalone executables for the current platform using PyInstaller.

Usage:
    python scripts/build.py [--onedir]

Options:
    --onedir    Create a one-directory bundle instead of a single file
"""

import argparse
import platform
import shutil
import subprocess
import sys
from pathlib import Path


def get_platform_suffix() -> str:
    """Get a platform-specific suffix for the executable name."""
    system = platform.system().lower()
    machine = platform.machine().lower()

    # Normalize machine architecture names
    if machine in ('x86_64', 'amd64'):
        machine = 'x86_64'
    elif machine in ('arm64', 'aarch64'):
        machine = 'arm64'
    elif machine in ('i386', 'i686'):
        machine = 'x86'

    return f"{system}-{machine}"


def build(onedir: bool = False) -> Path:
    """Build the executable."""
    project_root = Path(__file__).parent.parent
    dist_dir = project_root / "dist"

    # Clean previous builds
    if dist_dir.exists():
        shutil.rmtree(dist_dir)

    build_dir = project_root / "build"
    if build_dir.exists():
        shutil.rmtree(build_dir)

    # Build command
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--name", "termlogger",
        "--console",
        "--add-data", f"{project_root / 'termlogger.css'}:.",
        "--collect-all", "textual",
        "--hidden-import", "pydantic",
        "--hidden-import", "pydantic_core",
        "--hidden-import", "httpx",
        "--hidden-import", "httpcore",
        "--hidden-import", "h11",
        "--hidden-import", "anyio",
        "--hidden-import", "sniffio",
        "--hidden-import", "certifi",
        "--hidden-import", "idna",
        "--hidden-import", "dateutil",
        "--hidden-import", "xmltodict",
        "--hidden-import", "rich",
        "--hidden-import", "markdown_it",
        "--hidden-import", "pygments",
        "--exclude-module", "tkinter",
        "--exclude-module", "matplotlib",
        "--exclude-module", "numpy",
        "--exclude-module", "pandas",
    ]

    if onedir:
        cmd.append("--onedir")
    else:
        cmd.append("--onefile")

    cmd.append(str(project_root / "src" / "termlogger" / "app.py"))

    print(f"Building TermLogger for {get_platform_suffix()}...")
    print(f"Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, cwd=project_root)

    if result.returncode != 0:
        print("Build failed!")
        sys.exit(1)

    # Rename with platform suffix
    suffix = get_platform_suffix()
    if platform.system() == "Windows":
        src = dist_dir / "termlogger.exe"
        dst = dist_dir / f"termlogger-{suffix}.exe"
    else:
        src = dist_dir / "termlogger"
        dst = dist_dir / f"termlogger-{suffix}"

    if src.exists() and not onedir:
        shutil.move(str(src), str(dst))
        print(f"Built: {dst}")
        return dst
    elif onedir:
        print(f"Built: {dist_dir / 'termlogger'}/")
        return dist_dir / "termlogger"
    else:
        print("Build output not found!")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(description="Build TermLogger executable")
    parser.add_argument(
        "--onedir",
        action="store_true",
        help="Create a one-directory bundle instead of a single file",
    )
    args = parser.parse_args()

    build(onedir=args.onedir)


if __name__ == "__main__":
    main()
