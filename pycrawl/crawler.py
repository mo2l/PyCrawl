"""
Main crawler module for PyCrawl - Detects broken links and resources
"""
import requests
from typing import Dict, List, Optional, Set, Tuple, Union
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("pycrawl")


@dataclass
class Resource:
    """Class representing a web resource (link, image, script, etc.)"""
    url: str
    resource_type: str  # 'link', 'image', 'script', 'stylesheet', etc.
    status_code: Optional[int] = None
    is_broken: bool = False
    error_message: Optional[str] = None
    source_url: Optional[str] = None  # URL where this resource was found


class BrokenLinkChecker:
    """
    A crawler that searches for broken links and resources on websites.
    """

    def __init__(
        self, 
        base_url: str, 
        max_depth: int = 2, 
        max_workers: int = 10,
        timeout: int = 10,
        user_agent: str = "PyCrawl/0.1.0",
        auth: Optional[Tuple[str, str]] = None
    ):
        """
        Initialize the crawler with a base URL and configuration.

        Args:
            base_url: The starting URL for the crawler
            max_depth: Maximum depth to crawl (default: 2)
            max_workers: Maximum number of concurrent workers (default: 10)
            timeout: Timeout for HTTP requests in seconds (default: 10)
            user_agent: User agent string to use for requests (default: PyCrawl/0.1.0)
            auth: Optional tuple of (username, password) for HTTP Basic Authentication
        """
        self.base_url = base_url
        self.max_depth = max_depth
        self.max_workers = max_workers
        self.timeout = timeout
        self.user_agent = user_agent
        self.auth = auth

        # Initialize tracking sets and dictionaries
        self.visited_urls: Set[str] = set()
        self.queued_urls: Set[str] = set()
        self.broken_resources: List[Resource] = []
        self.all_resources: Dict[str, Resource] = {}

        # Parse the base URL to get the domain
        self.base_domain = urlparse(base_url).netloc

        # Headers for requests
        self.headers = {
            "User-Agent": self.user_agent
        }

    def is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid and has the same domain as the base URL.

        Args:
            url: URL to check

        Returns:
            bool: True if the URL is valid, False otherwise
        """
        try:
            parsed_url = urlparse(url)
            return bool(parsed_url.netloc) and parsed_url.netloc == self.base_domain
        except Exception:
            return False

    def normalize_url(self, url: str, source_url: Optional[str] = None) -> str:
        """
        Normalize a URL by resolving relative URLs and removing fragments.

        Args:
            url: URL to normalize
            source_url: Source URL where this URL was found

        Returns:
            str: Normalized URL
        """
        # Handle relative URLs
        if source_url and not bool(urlparse(url).netloc):
            url = urljoin(source_url, url)

        # Remove fragments
        parsed = urlparse(url)
        return parsed._replace(fragment="").geturl()

    def fetch_url(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """
        Fetch the content of a URL.

        Args:
            url: URL to fetch

        Returns:
            Tuple containing:
            - HTML content of the page or None if the request failed
            - Status code or None if the request failed
            - Error message or None if the request succeeded
        """
        try:
            response = requests.get(
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                auth=self.auth
            )
            response.raise_for_status()
            return response.text, response.status_code, None
        except requests.exceptions.HTTPError as e:
            # Return the status code for HTTP errors
            return None, e.response.status_code, str(e)
        except Exception as e:
            # For other errors, return None for status code
            return None, None, str(e)

    def check_resource(self, resource: Resource) -> Resource:
        """
        Check if a resource is broken.

        Args:
            resource: Resource to check

        Returns:
            Resource: Updated resource with status information
        """
        try:
            # For links, we do a HEAD request first to save bandwidth
            method = "HEAD" if resource.resource_type == "link" else "GET"
            response = requests.request(
                method, 
                resource.url, 
                headers=self.headers, 
                timeout=self.timeout,
                auth=self.auth
            )

            # If HEAD request fails, try GET as some servers don't support HEAD
            if method == "HEAD" and response.status_code >= 400:
                response = requests.get(
                    resource.url, 
                    headers=self.headers, 
                    timeout=self.timeout,
                    auth=self.auth
                )

            resource.status_code = response.status_code
            resource.is_broken = response.status_code >= 400

            if resource.is_broken:
                resource.error_message = f"HTTP Error: {response.status_code}"

        except requests.exceptions.RequestException as e:
            resource.is_broken = True
            resource.error_message = str(e)

        return resource

    def extract_resources(self, html: str, source_url: str) -> List[Resource]:
        """
        Extract all resources (links, images, scripts, stylesheets) from HTML.

        Args:
            html: HTML content to parse
            source_url: URL where this HTML was found

        Returns:
            List[Resource]: List of resources found in the HTML
        """
        resources = []
        soup = BeautifulSoup(html, "html.parser")

        # Extract links (a href)
        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"]
            # Skip mailto, tel, javascript, and anchor links
            if href.startswith(("mailto:", "tel:", "javascript:")) or href == "#":
                continue

            url = self.normalize_url(href, source_url)
            resources.append(Resource(
                url=url,
                resource_type="link",
                source_url=source_url
            ))

        # Extract images (img src)
        for img_tag in soup.find_all("img", src=True):
            src = img_tag["src"]
            url = self.normalize_url(src, source_url)
            resources.append(Resource(
                url=url,
                resource_type="image",
                source_url=source_url
            ))

        # Extract stylesheets (link rel="stylesheet")
        for link_tag in soup.find_all("link", rel="stylesheet", href=True):
            href = link_tag["href"]
            url = self.normalize_url(href, source_url)
            resources.append(Resource(
                url=url,
                resource_type="stylesheet",
                source_url=source_url
            ))

        # Extract scripts (script src)
        for script_tag in soup.find_all("script", src=True):
            src = script_tag["src"]
            url = self.normalize_url(src, source_url)
            resources.append(Resource(
                url=url,
                resource_type="script",
                source_url=source_url
            ))

        return resources

    def crawl(self) -> Dict[str, List[Resource]]:
        """
        Start crawling from the base URL and check for broken links and resources.

        Returns:
            Dict[str, List[Resource]]: Dictionary mapping resource types to lists of broken resources
        """
        # Add the base URL to the queue
        self.queued_urls.add(self.base_url)

        # Process URLs up to max_depth
        for depth in range(self.max_depth + 1):
            logger.info(f"Crawling at depth {depth}/{self.max_depth}")

            # Get the URLs to process at this depth
            urls_to_process = list(self.queued_urls - self.visited_urls)
            if not urls_to_process:
                break

            # Mark these URLs as visited
            self.visited_urls.update(urls_to_process)

            # Clear the queue for the next depth
            self.queued_urls = set()

            # Process URLs in parallel
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                # Process each URL
                for url in urls_to_process:
                    executor.submit(self._process_url, url, depth)

        # Return the broken resources grouped by type
        return self._group_broken_resources()

    def _process_url(self, url: str, depth: int) -> None:
        """
        Process a single URL: fetch it, extract resources, and check them.

        Args:
            url: URL to process
            depth: Current crawl depth
        """
        logger.info(f"Processing URL: {url}")

        # Fetch the URL
        html, status_code, error = self.fetch_url(url)

        # If the URL is broken, add it to the broken resources
        if error:
            resource = Resource(
                url=url,
                resource_type="link",
                status_code=status_code,
                is_broken=True,
                error_message=error
            )
            self.broken_resources.append(resource)
            self.all_resources[url] = resource
            return

        # Extract resources from the HTML
        resources = self.extract_resources(html, url)

        # Check each resource
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            future_to_resource = {
                executor.submit(self.check_resource, resource): resource 
                for resource in resources
            }

            for future in future_to_resource:
                resource = future.result()
                self.all_resources[resource.url] = resource

                if resource.is_broken:
                    self.broken_resources.append(resource)
                elif resource.resource_type == "link" and depth < self.max_depth:
                    # Only add links to the queue if they're valid and we haven't reached max depth
                    if self.is_valid_url(resource.url) and resource.url not in self.visited_urls:
                        self.queued_urls.add(resource.url)

    def _group_broken_resources(self) -> Dict[str, List[Resource]]:
        """
        Group broken resources by type.

        Returns:
            Dict[str, List[Resource]]: Dictionary mapping resource types to lists of broken resources
        """
        result: Dict[str, List[Resource]] = {}

        for resource in self.broken_resources:
            if resource.resource_type not in result:
                result[resource.resource_type] = []
            result[resource.resource_type].append(resource)

        return result

    def generate_report(self) -> str:
        """
        Generate a human-readable report of broken resources.

        Returns:
            str: Report of broken resources
        """
        if not self.broken_resources:
            return "No broken resources found."

        report = ["# Broken Resources Report", ""]

        # Group by type
        grouped = self._group_broken_resources()

        for resource_type, resources in grouped.items():
            report.append(f"## {resource_type.capitalize()} ({len(resources)})")

            for resource in resources:
                status = f"Status: {resource.status_code}" if resource.status_code else "Connection Error"
                error = f"Error: {resource.error_message}" if resource.error_message else ""
                source = f"Found on: {resource.source_url}" if resource.source_url else ""

                report.append(f"- {resource.url}")
                report.append(f"  {status}")
                if error:
                    report.append(f"  {error}")
                if source:
                    report.append(f"  {source}")
                report.append("")

        return "\n".join(report)

    def get_statistics(self) -> Dict[str, Union[int, float]]:
        """
        Get statistics about the crawl.

        Returns:
            Dict[str, Union[int, float]]: Dictionary of statistics
        """
        total_resources = len(self.all_resources)
        broken_count = len(self.broken_resources)

        # Count by type
        resource_types = {}
        broken_by_type = {}

        for resource in self.all_resources.values():
            # Count by type
            if resource.resource_type not in resource_types:
                resource_types[resource.resource_type] = 0
            resource_types[resource.resource_type] += 1

            # Count broken by type
            if resource.is_broken:
                if resource.resource_type not in broken_by_type:
                    broken_by_type[resource.resource_type] = 0
                broken_by_type[resource.resource_type] += 1

        return {
            "total_urls_crawled": len(self.visited_urls),
            "total_resources": total_resources,
            "broken_resources": broken_count,
            "broken_percentage": (broken_count / total_resources * 100) if total_resources > 0 else 0,
            "resource_types": resource_types,
            "broken_by_type": broken_by_type
        }
