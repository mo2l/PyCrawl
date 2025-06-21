# PyCrawl - Broken Link Checker

A Python web crawler that searches for broken links and resources on websites.

## Features

- Crawls websites and checks for broken links and resources
- Validates different types of resources (links, images, stylesheets, scripts)
- Generates detailed reports of broken resources
- Provides statistics about the crawl
- Supports concurrent requests for faster crawling
- Configurable crawl depth, timeout, and user agent
- Supports HTTP Basic Authentication for protected sites

## Installation

```bash
# Clone the repository
git clone git@github.com:mo2l/PyCrawl.git
cd PyCrawl

# Install the package
pip install -e .
```

## Usage

### As a Python Module

```python
from pycrawl.crawler import BrokenLinkChecker

# Create a checker
checker = BrokenLinkChecker(
    base_url="https://example.com",
    max_depth=2,
    max_workers=10,
    timeout=10,
    user_agent="PyCrawl/0.1.0"
)

# Create a checker with HTTP Basic Authentication
checker_with_auth = BrokenLinkChecker(
    base_url="https://example.com",
    max_depth=2,
    max_workers=10,
    timeout=10,
    user_agent="PyCrawl/0.1.0",
    auth=("username", "password")  # HTTP Basic Authentication
)

# Start crawling
broken_resources = checker.crawl()

# Generate a report
report = checker.generate_report()
print(report)

# Get statistics
stats = checker.get_statistics()
print(f"Total URLs crawled: {stats['total_urls_crawled']}")
print(f"Total resources checked: {stats['total_resources']}")
print(f"Broken resources: {stats['broken_resources']}")
```

### Command Line Tool

PyCrawl includes a command-line tool for finding broken links:

```bash
# Run the example script
python -m pycrawl.examples.find_broken_links https://example.com

# Specify crawl depth
python -m pycrawl.examples.find_broken_links https://example.com --depth 3

# Save the report to a file
python -m pycrawl.examples.find_broken_links https://example.com --output report.md

# Use HTTP Basic Authentication
python -m pycrawl.examples.find_broken_links https://example.com --username myuser --password mypass

# Get help
python -m pycrawl.examples.find_broken_links --help
```

## Example Output

```
# Broken Resources Report

## Link (2)
- https://example.com/broken-page
  Status: 404
  Error: HTTP Error: 404
  Found on: https://example.com

- https://example.com/another-broken-page
  Status: 500
  Error: HTTP Error: 500
  Found on: https://example.com/about

## Image (1)
- https://example.com/missing-image.jpg
  Status: 404
  Error: HTTP Error: 404
  Found on: https://example.com/gallery

Crawl Statistics:
Total URLs crawled: 10
Total resources checked: 50
Broken resources: 3 (6.0%)

Broken resources by type:
  link: 2
  image: 1
```

## Development

### Setting Up Development Environment

```bash
# Create a virtual environment
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate

# Install development dependencies
pip install -r requirements.txt
pip install -e .
```

### Running Tests

```bash
# Run all tests
python -m pytest

# Run with coverage
python -m pytest --cov=pycrawl
```

## License

This project is licensed under the MIT License - see the LICENSE file for details.
