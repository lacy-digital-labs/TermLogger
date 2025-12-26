# Release Process

This document describes the release process for TermLogger.

## Version Numbering

TermLogger uses **calendar-based versioning** with the format:

```
YY.MM.nn
```

| Component | Description | Example |
|-----------|-------------|---------|
| `YY` | Two-digit year | `25` for 2025 |
| `MM` | Two-digit month | `12` for December |
| `nn` | Release number within the month | `01`, `02`, etc. |

### Examples

| Version | Meaning |
|---------|---------|
| `25.12.01` | First release in December 2025 |
| `25.12.02` | Second release in December 2025 |
| `26.01.01` | First release in January 2026 |

### Version Precedence

Versions sort naturally:
- `25.11.02` < `25.12.01` < `26.01.01`

## Release Types

### Regular Releases

Normal releases with new features, improvements, and bug fixes.

### Hotfix Releases

Emergency fixes that need immediate release. Simply increment the `nn` component:
- If current is `25.12.01`, hotfix becomes `25.12.02`

## Pre-Release Checklist

Before creating a release:

- [ ] All tests pass: `pytest tests/`
- [ ] No linting errors: `ruff check src/`
- [ ] Version updated in `pyproject.toml`
- [ ] CHANGELOG.md updated with release notes
- [ ] Documentation is current
- [ ] All changes committed to main branch

## Release Procedure

### 1. Update Version

Edit `pyproject.toml`:

```toml
[project]
version = "YY.MM.nn"
```

### 2. Update Changelog

Add a new section to `CHANGELOG.md`:

```markdown
## [YY.MM.nn] - YYYY-MM-DD

### Added
- New feature description

### Changed
- Change description

### Fixed
- Bug fix description
```

### 3. Commit Changes

```bash
git add pyproject.toml CHANGELOG.md
git commit -m "Release YY.MM.nn"
```

### 4. Create Git Tag

```bash
git tag -a vYY.MM.nn -m "Version YY.MM.nn"
```

### 5. Push to Remote

```bash
git push origin main
git push origin vYY.MM.nn
```

### 6. Create GitHub Release

1. Go to the repository's Releases page
2. Click "Draft a new release"
3. Select the tag `vYY.MM.nn`
4. Title: `TermLogger YY.MM.nn`
5. Copy release notes from CHANGELOG.md
6. Attach any binary distributions
7. Publish release

## Building Distributions

### Source Distribution

```bash
python -m build --sdist
```

### Wheel Distribution

```bash
python -m build --wheel
```

### Standalone Executable (Optional)

Using PyInstaller:

```bash
pip install pyinstaller
pyinstaller --onefile --name termlogger src/termlogger/app.py
```

The executable will be in `dist/termlogger`.

## Post-Release

After a successful release:

1. Announce the release (mailing list, social media, etc.)
2. Monitor for any immediate issues
3. Start planning the next release

## Rollback Procedure

If a release has critical issues:

1. **Immediate**: Delete the GitHub release (keeps the tag)
2. **Fix**: Create a hotfix release with `nn` incremented
3. **Document**: Note the issue in CHANGELOG.md

Do NOT delete git tags after pushing - this can cause issues for users who have already pulled them.

## Changelog Guidelines

### Categories

Use these categories in CHANGELOG.md:

| Category | Use For |
|----------|---------|
| **Added** | New features |
| **Changed** | Changes to existing functionality |
| **Deprecated** | Features to be removed in future |
| **Removed** | Features removed in this release |
| **Fixed** | Bug fixes |
| **Security** | Security-related fixes |

### Writing Good Release Notes

- Write from the user's perspective
- Be concise but informative
- Include issue/PR references when applicable
- Group related changes together

**Good:**
```markdown
- Added POTA Hunter mode for tracking park contacts without activation requirements (#42)
```

**Not as good:**
```markdown
- Refactored mode selection to support string-based mode types
```

## Semantic Versioning Comparison

Unlike semantic versioning (MAJOR.MINOR.PATCH), calendar versioning:

| Aspect | SemVer | CalVer (YY.MM.nn) |
|--------|--------|-------------------|
| Breaking changes | Bump MAJOR | Any release |
| New features | Bump MINOR | Any release |
| Bug fixes | Bump PATCH | Any release |
| Time indication | None | Built-in |
| Predictability | Based on changes | Based on calendar |

Calendar versioning works well for applications with regular release cycles and where users benefit from knowing how recent their version is.
