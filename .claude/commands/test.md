# Test Runner

Run Python tests with pytest, unittest, or other testing frameworks.

## Purpose

This command helps you run Python tests effectively with proper configuration and reporting.

## Usage

```
/test
```

## What this command does

1. **Detects test framework** (pytest, unittest, nose2)
2. **Runs appropriate tests** with proper configuration
3. **Provides coverage reporting** if available
4. **Shows clear test results** with failure details

## Example Commands

### pytest (recommended)
```bash
# Run all tests
uv run pytest

# Run with coverage
uv run pytest --cov=src --cov-report=html

# Run specific test file
uv run pytest tests/test_models.py

# Run with verbose output
uv run pytest -v

# Run tests matching pattern
uv run pytest -k "test_user"
```

### unittest
```bash
# Run all tests
uv run python -m unittest discover

# Run specific test file
uv run python -m unittest tests.test_models

# Run with verbose output
uv run python -m unittest -v
```

### Django tests
```bash
# Run all Django tests
uv run python manage.py test

# Run specific app tests
uv run python manage.py test myapp

# Run with coverage
uv run coverage run --source='.' manage.py test
uv run coverage report
```

## Best Practices

- Write tests for all critical functionality
- Use descriptive test names
- Keep tests isolated and independent
- Mock external dependencies
- Aim for high test coverage (80%+)
