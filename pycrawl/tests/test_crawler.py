"""
Tests for the crawler module
"""
import pytest
import requests
from unittest.mock import patch, MagicMock
from bs4 import BeautifulSoup
from pycrawl.crawler import BrokenLinkChecker, Resource


class TestBrokenLinkChecker:
    """Test suite for the BrokenLinkChecker class"""

    def test_init(self):
        """Test crawler initialization"""
        checker = BrokenLinkChecker("https://example.com", max_depth=3)
        assert checker.base_url == "https://example.com"
        assert checker.max_depth == 3
        assert checker.visited_urls == set()
        assert checker.base_domain == "example.com"
        assert checker.auth is None

        # Test with auth
        auth = ("username", "password")
        checker_with_auth = BrokenLinkChecker("https://example.com", auth=auth)
        assert checker_with_auth.auth == auth

    def test_is_valid_url(self):
        """Test URL validation"""
        checker = BrokenLinkChecker("https://example.com")

        # Valid URLs (same domain)
        assert checker.is_valid_url("https://example.com/page1")
        assert checker.is_valid_url("https://example.com/page2?param=value")

        # Invalid URLs (different domain)
        assert not checker.is_valid_url("https://another-domain.com")
        assert not checker.is_valid_url("http://subdomain.example.com")  # Different netloc

        # Invalid URL format
        assert not checker.is_valid_url("not-a-url")

    def test_normalize_url(self):
        """Test URL normalization"""
        checker = BrokenLinkChecker("https://example.com")

        # Absolute URL
        assert checker.normalize_url("https://example.com/page") == "https://example.com/page"

        # Relative URL
        assert checker.normalize_url("/page", "https://example.com") == "https://example.com/page"

        # URL with fragment
        assert checker.normalize_url("https://example.com/page#section") == "https://example.com/page"

        # Relative URL with fragment
        assert checker.normalize_url("/page#section", "https://example.com") == "https://example.com/page"

    @patch("pycrawl.crawler.requests.get")
    def test_fetch_url_success(self, mock_get):
        """Test successful URL fetching"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "<html>Test content</html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        checker = BrokenLinkChecker("https://example.com")
        html, status_code, error = checker.fetch_url("https://example.com/page")

        # Verify
        assert html == "<html>Test content</html>"
        assert status_code == 200
        assert error is None
        mock_get.assert_called_once_with(
            "https://example.com/page", 
            headers={"User-Agent": "PyCrawl/0.1.0"}, 
            timeout=10,
            auth=None
        )

    @patch("pycrawl.crawler.requests.get")
    def test_fetch_url_with_auth(self, mock_get):
        """Test URL fetching with authentication"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.text = "<html>Test content</html>"
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        auth = ("username", "password")
        checker = BrokenLinkChecker("https://example.com", auth=auth)
        html, status_code, error = checker.fetch_url("https://example.com/page")

        # Verify
        assert html == "<html>Test content</html>"
        assert status_code == 200
        assert error is None
        mock_get.assert_called_once_with(
            "https://example.com/page", 
            headers={"User-Agent": "PyCrawl/0.1.0"}, 
            timeout=10,
            auth=auth
        )

    @patch("pycrawl.crawler.requests.get")
    def test_fetch_url_http_error(self, mock_get):
        """Test URL fetching with HTTP error"""
        # Setup mock to raise an HTTP error
        mock_response = MagicMock()
        http_error = requests.exceptions.HTTPError("404 Client Error")
        http_error.response = MagicMock()
        http_error.response.status_code = 404
        mock_response.raise_for_status.side_effect = http_error
        mock_response.status_code = 404
        mock_get.return_value = mock_response

        checker = BrokenLinkChecker("https://example.com")
        html, status_code, error = checker.fetch_url("https://example.com/page")

        # Verify
        assert html is None
        assert status_code == 404
        assert "404 Client Error" in error
        mock_get.assert_called_once()

    @patch("pycrawl.crawler.requests.get")
    def test_fetch_url_connection_error(self, mock_get):
        """Test URL fetching with connection error"""
        # Setup mock to raise a connection error
        mock_get.side_effect = requests.exceptions.ConnectionError("Connection refused")

        checker = BrokenLinkChecker("https://example.com")
        html, status_code, error = checker.fetch_url("https://example.com/page")

        # Verify
        assert html is None
        assert status_code is None
        assert "Connection refused" in error
        mock_get.assert_called_once()

    @patch("pycrawl.crawler.requests.request")
    def test_check_resource_success(self, mock_request):
        """Test successful resource checking"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        checker = BrokenLinkChecker("https://example.com")
        resource = Resource(url="https://example.com/image.jpg", resource_type="image")
        result = checker.check_resource(resource)

        # Verify
        assert result.status_code == 200
        assert not result.is_broken
        assert result.error_message is None
        mock_request.assert_called_once_with(
            "GET", 
            "https://example.com/image.jpg", 
            headers={"User-Agent": "PyCrawl/0.1.0"}, 
            timeout=10,
            auth=None
        )

    @patch("pycrawl.crawler.requests.request")
    def test_check_resource_with_auth(self, mock_request):
        """Test resource checking with authentication"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_request.return_value = mock_response

        auth = ("username", "password")
        checker = BrokenLinkChecker("https://example.com", auth=auth)
        resource = Resource(url="https://example.com/image.jpg", resource_type="image")
        result = checker.check_resource(resource)

        # Verify
        assert result.status_code == 200
        assert not result.is_broken
        assert result.error_message is None
        mock_request.assert_called_once_with(
            "GET", 
            "https://example.com/image.jpg", 
            headers={"User-Agent": "PyCrawl/0.1.0"}, 
            timeout=10,
            auth=auth
        )

    @patch("pycrawl.crawler.requests.request")
    def test_check_resource_broken(self, mock_request):
        """Test broken resource checking"""
        # Setup mock
        mock_response = MagicMock()
        mock_response.status_code = 404
        mock_request.return_value = mock_response

        checker = BrokenLinkChecker("https://example.com")
        resource = Resource(url="https://example.com/image.jpg", resource_type="image")
        result = checker.check_resource(resource)

        # Verify
        assert result.status_code == 404
        assert result.is_broken
        assert "HTTP Error: 404" in result.error_message
        mock_request.assert_called_once()

    @patch("pycrawl.crawler.requests.request")
    @patch("pycrawl.crawler.requests.get")
    def test_check_resource_head_fallback(self, mock_get, mock_request):
        """Test HEAD request fallback to GET for links"""
        # Setup mocks
        head_response = MagicMock()
        head_response.status_code = 405  # Method Not Allowed
        mock_request.return_value = head_response

        get_response = MagicMock()
        get_response.status_code = 200
        mock_get.return_value = get_response

        checker = BrokenLinkChecker("https://example.com")
        resource = Resource(url="https://example.com/page", resource_type="link")
        result = checker.check_resource(resource)

        # Verify
        assert result.status_code == 200
        assert not result.is_broken
        mock_request.assert_called_once_with(
            "HEAD", 
            "https://example.com/page", 
            headers={"User-Agent": "PyCrawl/0.1.0"}, 
            timeout=10,
            auth=None
        )
        mock_get.assert_called_once()

    def test_extract_resources(self):
        """Test resource extraction from HTML"""
        html = """
        <html>
        <head>
            <link rel="stylesheet" href="/styles.css">
            <script src="/script.js"></script>
        </head>
        <body>
            <a href="/page1">Link 1</a>
            <a href="https://example.com/page2">Link 2</a>
            <a href="mailto:info@example.com">Email</a>
            <a href="#">Anchor</a>
            <img src="/image.jpg" alt="Image">
        </body>
        </html>
        """

        checker = BrokenLinkChecker("https://example.com")
        resources = checker.extract_resources(html, "https://example.com")

        # Verify
        assert len(resources) == 5  # 2 links, 1 image, 1 stylesheet, 1 script

        # Check resource types
        resource_types = [r.resource_type for r in resources]
        assert resource_types.count("link") == 2
        assert resource_types.count("image") == 1
        assert resource_types.count("stylesheet") == 1
        assert resource_types.count("script") == 1

        # Check URLs
        urls = [r.url for r in resources]
        assert "https://example.com/page1" in urls
        assert "https://example.com/page2" in urls
        assert "https://example.com/image.jpg" in urls
        assert "https://example.com/styles.css" in urls
        assert "https://example.com/script.js" in urls

        # Check that mailto and anchor links are skipped
        assert "mailto:info@example.com" not in urls
        assert "#" not in urls

    @patch.object(BrokenLinkChecker, "fetch_url")
    @patch.object(BrokenLinkChecker, "extract_resources")
    @patch.object(BrokenLinkChecker, "check_resource")
    def test_process_url(self, mock_check_resource, mock_extract_resources, mock_fetch_url):
        """Test URL processing"""
        # Setup mocks
        mock_fetch_url.return_value = ("<html></html>", 200, None)

        resource1 = Resource(url="https://example.com/page1", resource_type="link")
        resource2 = Resource(url="https://example.com/image.jpg", resource_type="image")
        mock_extract_resources.return_value = [resource1, resource2]

        # Mock check_resource to return the resource with status
        def check_resource_side_effect(resource):
            resource.status_code = 200
            resource.is_broken = False
            return resource

        mock_check_resource.side_effect = check_resource_side_effect

        # Create checker and process URL
        checker = BrokenLinkChecker("https://example.com")
        checker._process_url("https://example.com", 0)

        # Verify
        mock_fetch_url.assert_called_once_with("https://example.com")
        mock_extract_resources.assert_called_once_with("<html></html>", "https://example.com")
        assert mock_check_resource.call_count == 2

        # Check that resources were added to all_resources
        assert len(checker.all_resources) == 2
        assert "https://example.com/page1" in checker.all_resources
        assert "https://example.com/image.jpg" in checker.all_resources

        # Check that no broken resources were found
        assert len(checker.broken_resources) == 0

        # Check that valid links were added to queued_urls
        assert "https://example.com/page1" in checker.queued_urls

        # Images should not be added to queued_urls
        assert "https://example.com/image.jpg" not in checker.queued_urls

    def test_group_broken_resources(self):
        """Test grouping of broken resources by type"""
        checker = BrokenLinkChecker("https://example.com")

        # Add some broken resources
        checker.broken_resources = [
            Resource(url="https://example.com/page1", resource_type="link", is_broken=True),
            Resource(url="https://example.com/page2", resource_type="link", is_broken=True),
            Resource(url="https://example.com/image.jpg", resource_type="image", is_broken=True),
            Resource(url="https://example.com/styles.css", resource_type="stylesheet", is_broken=True)
        ]

        # Group resources
        grouped = checker._group_broken_resources()

        # Verify
        assert len(grouped) == 3
        assert len(grouped["link"]) == 2
        assert len(grouped["image"]) == 1
        assert len(grouped["stylesheet"]) == 1

    def test_generate_report(self):
        """Test report generation"""
        checker = BrokenLinkChecker("https://example.com")

        # Test with no broken resources
        assert "No broken resources found" in checker.generate_report()

        # Add some broken resources
        checker.broken_resources = [
            Resource(
                url="https://example.com/page1", 
                resource_type="link", 
                is_broken=True, 
                status_code=404,
                error_message="HTTP Error: 404",
                source_url="https://example.com"
            ),
            Resource(
                url="https://example.com/image.jpg", 
                resource_type="image", 
                is_broken=True, 
                status_code=404,
                error_message="HTTP Error: 404",
                source_url="https://example.com/page1"
            )
        ]

        # Generate report
        report = checker.generate_report()

        # Verify
        assert "# Broken Resources Report" in report
        assert "## Link (1)" in report
        assert "## Image (1)" in report
        assert "https://example.com/page1" in report
        assert "https://example.com/image.jpg" in report
        assert "Status: 404" in report
        assert "Error: HTTP Error: 404" in report
        assert "Found on: https://example.com" in report
        assert "Found on: https://example.com/page1" in report

    def test_get_statistics(self):
        """Test statistics generation"""
        checker = BrokenLinkChecker("https://example.com")

        # Add visited URLs
        checker.visited_urls = {"https://example.com", "https://example.com/page1"}

        # Add resources
        checker.all_resources = {
            "https://example.com/page1": Resource(url="https://example.com/page1", resource_type="link"),
            "https://example.com/page2": Resource(url="https://example.com/page2", resource_type="link", is_broken=True),
            "https://example.com/image.jpg": Resource(url="https://example.com/image.jpg", resource_type="image"),
            "https://example.com/styles.css": Resource(url="https://example.com/styles.css", resource_type="stylesheet", is_broken=True)
        }

        # Add broken resources
        checker.broken_resources = [
            checker.all_resources["https://example.com/page2"],
            checker.all_resources["https://example.com/styles.css"]
        ]

        # Get statistics
        stats = checker.get_statistics()

        # Verify
        assert stats["total_urls_crawled"] == 2
        assert stats["total_resources"] == 4
        assert stats["broken_resources"] == 2
        assert stats["broken_percentage"] == 50.0
        assert stats["resource_types"]["link"] == 2
        assert stats["resource_types"]["image"] == 1
        assert stats["resource_types"]["stylesheet"] == 1
        assert stats["broken_by_type"]["link"] == 1
        assert stats["broken_by_type"]["stylesheet"] == 1
