# PyCrawl Development Guidelines

This document provides essential information for developers working on the PyCrawl project.

## Build/Configuration Instructions

### Environment Setup

1. **Python Version**: PyCrawl requires Python 3.8 or higher.

2. **Virtual Environment**: It's recommended to use a virtual environment for development:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. **Installation**:
   - For development, install in editable mode:
     ```bash
     pip install -r requirements.txt
     pip install -e .
     ```
   - For production use:
     ```bash
     pip install .
     ```

### Project Structure

```
pycrawl/
├── __init__.py       # Package initialization
├── crawler.py        # Main crawler implementation
├── examples/         # Example scripts
│   ├── __init__.py
│   └── find_broken_links.py  # Command-line tool for finding broken links
└── tests/            # Test directory
    ├── __init__.py
    └── test_crawler.py
```

## Testing Information

### Running Tests

PyCrawl uses pytest as its testing framework. Tests can be run using:

```bash
# Run all tests
python -m pytest

# Run with verbose output
python -m pytest -v

# Run with coverage report
python -m pytest --cov=pycrawl

# Run specific test file
python -m pytest pycrawl/tests/test_crawler.py

# Run specific test class or method
python -m pytest pycrawl/tests/test_crawler.py::TestCrawler::test_is_valid_url
```

### Test Configuration

The project includes a `pytest.ini` file that configures pytest with the following settings:
- Test discovery in the `pycrawl/tests` directory
- Test files must match the pattern `test_*.py`
- Test classes must start with `Test`
- Test functions must start with `test_`
- Code coverage reporting is enabled by default

### Adding New Tests

1. Create a new test file in the `pycrawl/tests` directory with a name starting with `test_`.
2. Import the module you want to test.
3. Create test classes that start with `Test` and test methods that start with `test_`.
4. Use pytest fixtures for setup and teardown if needed.

### Example Test

Here's a simple example of a test for the `is_valid_url` method:

```python
def test_is_valid_url():
    """Test URL validation"""
    crawler = Crawler("https://example.com")

    # Valid URLs (same domain)
    assert crawler.is_valid_url("https://example.com/page1")

    # Invalid URLs (different domain)
    assert not crawler.is_valid_url("https://another-domain.com")
```

### Mocking External Services

For tests that would normally make HTTP requests, use the `pytest-mock` library to mock the requests:

```python
@patch("pycrawl.crawler.requests.get")
def test_fetch_url_success(mock_get):
    """Test successful URL fetching"""
    # Setup mock
    mock_response = MagicMock()
    mock_response.text = "<html>Test content</html>"
    mock_get.return_value = mock_response

    crawler = Crawler("https://example.com")
    content = crawler.fetch_url("https://example.com/page")

    # Verify
    assert content == "<html>Test content</html>"
    mock_get.assert_called_once_with("https://example.com/page", timeout=10)
```

## Code Style and Quality

### Code Formatting

PyCrawl uses Black for code formatting with a line length of 100 characters:

```bash
# Format all Python files
black pycrawl

# Check formatting without making changes
black --check pycrawl
```

### Linting

Flake8 is used for linting:

```bash
# Lint all Python files
flake8 pycrawl
```

### Type Checking

Mypy is used for static type checking:

```bash
# Type check all Python files
mypy pycrawl
```

### Pre-commit Checks

Before committing code, run the following checks:

```bash
# Format code
black pycrawl

# Run linting
flake8 pycrawl

# Run type checking
mypy pycrawl

# Run tests with coverage
python -m pytest --cov=pycrawl
```

## Development Workflow

### Git Workflow

The project is hosted on GitHub at [mo2l/PyCrawl](https://github.com/mo2l/PyCrawl).

1. Clone the repository:
   ```bash
   git clone git@github.com:mo2l/PyCrawl.git
   cd PyCrawl
   ```

2. Create a new branch for your feature or bugfix:
   ```bash
   git checkout -b feature/your-feature-name
   # or
   git checkout -b fix/your-bugfix-name
   ```

3. Write tests for your changes.
4. Implement your changes.
5. Ensure all tests pass and code quality checks succeed.
6. Commit your changes with descriptive commit messages:
   ```bash
   git add .
   git commit -m "Add feature: your feature description"
   ```

7. Push your branch to GitHub:
   ```bash
   git push origin feature/your-feature-name
   ```

8. Create a pull request on GitHub.
9. Address any review comments and make necessary changes.
10. Once approved, your changes will be merged into the main branch.

## Authentication

PyCrawl supports HTTP Basic Authentication for crawling protected websites. This can be used in two ways:

### In Python Code

```python
from pycrawl.crawler import BrokenLinkChecker

# Create a checker with HTTP Basic Authentication
checker = BrokenLinkChecker(
    base_url="https://example.com",
    auth=("username", "password")  # HTTP Basic Authentication
)

# Start crawling
broken_resources = checker.crawl()
```

### From Command Line

```bash
# Use HTTP Basic Authentication
python -m pycrawl.examples.find_broken_links https://example.com --username myuser --password mypass
```

## Troubleshooting

- If you encounter import errors when running tests, make sure you've installed the package in development mode with `pip install -e .`.
- If tests are failing due to missing dependencies, ensure you've installed all requirements with `pip install -r requirements.txt`.
