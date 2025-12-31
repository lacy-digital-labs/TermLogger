# Contributing to TermLogger

Thank you for your interest in contributing to TermLogger! This document outlines the process for contributing and the terms under which contributions are accepted.

## Developer Certificate of Origin (DCO)

By contributing to this project, you agree to the Developer Certificate of Origin (DCO). This is a legally binding statement that you have the right to submit your contribution and that you agree to license it under the project's MIT license.

### What is the DCO?

The DCO is a lightweight way for contributors to certify that they wrote or otherwise have the right to submit the code they are contributing. The full text of the DCO is available at [developercertificate.org](https://developercertificate.org/) and is reproduced below:

```
Developer Certificate of Origin
Version 1.1

Copyright (C) 2004, 2006 The Linux Foundation and its contributors.

Everyone is permitted to copy and distribute verbatim copies of this
license document, but changing it is not allowed.

Developer's Certificate of Origin 1.1

By making a contribution to this project, I certify that:

(a) The contribution was created in whole or in part by me and I
    have the right to submit it under the open source license
    indicated in the file; or

(b) The contribution is based upon previous work that, to the best
    of my knowledge, is covered under an appropriate open source
    license and I have the right under that license to submit that
    work with modifications, whether created in whole or in part
    by me, under the same open source license (unless I am
    permitted to submit under a different license), as indicated
    in the file; or

(c) The contribution was provided directly to me by some other
    person who certified (a), (b) or (c) and I have not modified
    it.

(d) I understand and agree that this project and the contribution
    are public and that a record of the contribution (including all
    personal information I submit with it, including my sign-off) is
    maintained indefinitely and may be redistributed consistent with
    this project or the open source license(s) involved.
```

### How to Sign Off

You must sign off on each commit to certify that you agree to the DCO. Add a line at the end of your commit message:

```
Signed-off-by: Your Name <your.email@example.com>
```

You can do this automatically by using the `-s` flag when committing:

```bash
git commit -s -m "Your commit message"
```

**Important:** Use your real name (not a pseudonym) and a valid email address.

## How to Contribute

### Reporting Bugs

1. Check existing [issues](https://github.com/lacy-digital-labs/TermLogger/issues) to avoid duplicates
2. Create a new issue with:
   - Clear, descriptive title
   - Steps to reproduce
   - Expected vs actual behavior
   - TermLogger version and OS

### Suggesting Features

1. Check existing issues for similar suggestions
2. Create a new issue describing:
   - The use case or problem you're solving
   - Your proposed solution
   - Any alternatives you've considered

### Submitting Code

1. **Fork the repository** and create a branch for your changes
2. **Follow the code style** - run `ruff check src/` before committing
3. **Test your changes** - run `pytest tests/` to ensure tests pass
4. **Sign off your commits** - every commit must include `Signed-off-by`
5. **Submit a pull request** with:
   - Clear description of the changes
   - Reference to any related issues
   - Screenshots for UI changes

### Code Style

- Follow PEP 8 guidelines
- Use type hints for function parameters and return values
- Keep functions focused and reasonably sized
- Add docstrings for public functions and classes

### Commit Messages

- Use clear, descriptive commit messages
- Start with a verb (Add, Fix, Update, Remove, etc.)
- Keep the first line under 72 characters
- Reference issues when applicable: `Fixes #123`

## License

By contributing to TermLogger, you agree that your contributions will be licensed under the MIT License. You retain copyright to your contributions, but you grant Lacy Digital Labs, LLC and all other users a perpetual, irrevocable license to use, modify, and distribute your contributions under the MIT License terms.

## Questions?

If you have questions about contributing, feel free to open an issue or reach out to the maintainers.

Thank you for contributing to TermLogger!
