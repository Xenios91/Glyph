# Contributing to Glyph

Thank you for your interest in contributing to Glyph! This document provides guidelines and instructions for contributing.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Development Setup](#development-setup)
- [Submitting Changes](#submitting-changes)
- [Coding Standards](#coding-standards)
- [Testing](#testing)
- [Documentation](#documentation)
- [Pull Request Process](#pull-request-process)

## Code of Conduct

This project follows a standard code of conduct. By participating, you are expected to uphold this standard. Be respectful, inclusive, and constructive in all interactions.

## Getting Started

1. Fork the repository on GitHub.
2. Clone your fork locally:
   ```bash
   git clone https://github.com/your-username/glyph.git
   cd glyph
   ```
3. Add the upstream remote:
   ```bash
   git remote add upstream https://github.com/original-owner/glyph.git
   ```

## Development Setup

### Prerequisites

- Python 3.11, 3.12, or 3.13
- [Ghidra](https://ghidra-sre.org/) (for binary decompilation)
- [uv](https://github.com/astral-sh/uv) (recommended for fast dependency management)

### Setting Up the Environment

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install dependencies
pip install .[dev]

# Install pre-commit hooks
pre-commit install

# Install Playwright browsers (for E2E tests)
playwright install chromium
```

### Configuration

Copy and modify the configuration file:

```bash
cp config.yml config.local.yml
```

Update `config.local.yml` with your settings, especially:
- `jwt_secret_key`: Use a strong random secret
- `cpu_cores`: Set to your available cores
- `upload_folder`: Path for binary storage

## Submitting Changes

### Branch Naming

Use descriptive branch names with prefixes:
- `feature/add-new-endpoint`
- `fix/resolve-auth-bug`
- `docs/update-api-reference`
- `refactor/cleanup-pipeline`
- `test/add-jwt-tests`

### Commit Messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```
type(scope): description

[optional body]

[optional footer]
```

Types:
- `feat`: New feature
- `fix`: Bug fix
- `docs`: Documentation changes
- `style`: Code style changes (formatting, etc.)
- `refactor`: Code refactoring
- `test`: Adding or modifying tests
- `chore`: Maintenance tasks

Examples:
```
feat(auth): add refresh token rotation
fix(api): handle null binary_id in predictions
docs: update API reference with new endpoints
```

## Coding Standards

### Linting and Formatting

This project uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
# Check for issues
ruff check .

# Auto-fix issues
ruff check --fix .

# Format code
ruff format .
```

### Type Checking

Use [mypy](https://mypy.readthedocs.io/) for static type checking:

```bash
mypy app/
```

### Pre-commit Hooks

Pre-commit hooks run automatically before each commit:

```bash
# Run all hooks manually
pre-commit run --all-files
```

## Testing

### Running Tests

```bash
# Run all unit tests
pytest tests/ --ignore=tests/e2e -v

# Run with coverage
pytest tests/ --ignore=tests/e2e --cov=app --cov-report=term-missing

# Run E2E tests
pytest tests/e2e -v

# Run specific test markers
pytest -m "not slow"  # Skip slow tests
pytest -m security    # Run security tests only
```

### Writing Tests

- Place unit tests in `tests/` mirroring the `app/` structure.
- E2E tests go in `tests/e2e/`.
- Use fixtures from `tests/conftest.py` for database and client setup.
- Follow the Arrange-Act-Assert pattern.
- Add `@pytest.mark.slow` for tests taking > 1 second.

Example:
```python
import pytest
from fastapi.testclient import TestClient

@pytest.mark.auth
async def test_login_success(test_client: TestClient) -> None:
    # Arrange
    response = test_client.post(
        "/auth/token",
        data={"username": "testuser", "password": "testpass"},
    )

    # Act & Assert
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
```

## Documentation

### Code Documentation

- All public functions must have docstrings following [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings).
- Document parameters, return values, and exceptions.
- Keep docstrings up to date with code changes.

### Architecture Documentation

Update `docs/ARCHITECTURE.md` when making structural changes. Include diagrams for new components.

### API Documentation

Update `docs/API_REFERENCE.md` when adding or modifying API endpoints.

## Pull Request Process

1. **Update your branch**: Rebase on the latest `main` branch.
   ```bash
   git fetch upstream
   git rebase upstream/main
   ```

2. **Run checks locally**:
   ```bash
   pre-commit run --all-files
   pytest tests/ --ignore=tests/e2e -v
   ```

3. **Create a Pull Request**:
   - Use a clear, descriptive title.
   - Reference related issues (e.g., "Closes #123").
   - Describe the changes and their purpose.
   - Include screenshots for UI changes.
   - List any breaking changes.

4. **Address Review Feedback**:
   - Respond to all comments.
   - Make requested changes in new commits.
   - Squash commits before merging (if requested).

5. **Merge**:
   - Wait for CI to pass.
   - Obtain at least one approval.
   - Squash and merge to keep history clean.

## Questions or Help?

- Open an [issue](https://github.com/original-owner/glyph/issues) for bugs or feature requests.
- Check existing issues and discussions before creating new ones.
