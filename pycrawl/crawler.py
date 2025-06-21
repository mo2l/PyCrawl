"""
Main crawler module for PyCrawl - Detects broken links and resources
"""
import requests
from typing import Dict, List, Optional, Set, Tuple, Union, Any
from urllib.parse import urljoin, urlparse
from bs4 import BeautifulSoup
import logging
import concurrent.futures
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
import time
from functools import lru_cache
import re

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

        # Performance metrics
        self.crawl_start_time: Optional[float] = None
        self.crawl_end_time: Optional[float] = None
        self.url_processing_times: Dict[str, float] = {}
        self.fetch_times: Dict[str, float] = {}
        self.extraction_times: Dict[str, float] = {}
        self.resource_check_times: Dict[str, float] = {}
        self.total_requests: int = 0

    @lru_cache(maxsize=1024)
    def is_valid_url(self, url: str) -> bool:
        """
        Check if a URL is valid and has the same domain as the base URL.
        Uses caching to avoid repeated parsing of the same URL.

        Args:
            url: URL to check

        Returns:
            bool: True if the URL is valid, False otherwise
        """
        try:
            # Quick check for common invalid URLs
            if not url or url.startswith(('javascript:', 'mailto:', 'tel:', '#')):
                return False

            parsed_url = urlparse(url)
            return bool(parsed_url.netloc) and parsed_url.netloc == self.base_domain
        except Exception:
            return False

    @lru_cache(maxsize=1024)
    def normalize_url(self, url: str, source_url: Optional[str] = None) -> str:
        """
        Normalize a URL by resolving relative URLs and removing fragments.
        Uses caching to avoid repeated processing of the same URL.

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

    @lru_cache(maxsize=1024)
    def fetch_url(self, url: str) -> Tuple[Optional[str], Optional[int], Optional[str]]:
        """
        Fetch the content of a URL with caching.

        Args:
            url: URL to fetch

        Returns:
            Tuple containing:
            - HTML content of the page or None if the request failed
            - Status code or None if the request failed
            - Error message or None if the request succeeded
        """
        try:
            logger.debug(f"Fetching URL: {url}")
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

    @lru_cache(maxsize=1024)
    def _check_url(self, url: str, method: str) -> Tuple[int, Optional[str]]:
        """
        Check a URL with caching.

        Args:
            url: URL to check
            method: HTTP method to use (HEAD or GET)

        Returns:
            Tuple containing:
            - Status code or None if the request failed
            - Error message or None if the request succeeded
        """
        try:
            logger.debug(f"Checking URL with {method}: {url}")
            response = requests.request(
                method, 
                url, 
                headers=self.headers, 
                timeout=self.timeout,
                auth=self.auth
            )
            return response.status_code, None
        except requests.exceptions.RequestException as e:
            return 0, str(e)

    def check_resource(self, resource: Resource) -> Resource:
        """
        Check if a resource is broken.

        Args:
            resource: Resource to check

        Returns:
            Resource: Updated resource with status information
        """
        # For links, we do a HEAD request first to save bandwidth
        method = "HEAD" if resource.resource_type == "link" else "GET"

        # Use cached check
        status_code, error = self._check_url(resource.url, method)

        # If HEAD request fails, try GET as some servers don't support HEAD
        if method == "HEAD" and status_code >= 400:
            status_code, error = self._check_url(resource.url, "GET")

        resource.status_code = status_code
        resource.is_broken = status_code >= 400 or error is not None

        if error:
            resource.error_message = error
        elif resource.is_broken:
            resource.error_message = f"HTTP Error: {status_code}"

        return resource

    def extract_resources(self, html: str, source_url: str) -> List[Resource]:
        """
        Extract all resources (links, images, scripts, stylesheets) from HTML.
        Optimized for performance with selective parsing.

        Args:
            html: HTML content to parse
            source_url: URL where this HTML was found

        Returns:
            List[Resource]: List of resources found in the HTML
        """
        resources = []

        # Use lxml parser for better performance if available
        try:
            soup = BeautifulSoup(html, "lxml")
        except:
            soup = BeautifulSoup(html, "html.parser")

        # Extract links (a href) - use CSS selector for better performance
        for a_tag in soup.select("a[href]"):
            href = a_tag.get("href", "")
            # Skip mailto, tel, javascript, and anchor links
            if not href or href.startswith(("mailto:", "tel:", "javascript:")) or href == "#":
                continue

            url = self.normalize_url(href, source_url)
            resources.append(Resource(
                url=url,
                resource_type="link",
                source_url=source_url
            ))

        # Extract images (img src)
        for img_tag in soup.select("img[src]"):
            src = img_tag.get("src", "")
            if not src:
                continue
            url = self.normalize_url(src, source_url)
            resources.append(Resource(
                url=url,
                resource_type="image",
                source_url=source_url
            ))

        # Extract stylesheets (link rel="stylesheet")
        for link_tag in soup.select("link[rel=stylesheet][href]"):
            href = link_tag.get("href", "")
            if not href:
                continue
            url = self.normalize_url(href, source_url)
            resources.append(Resource(
                url=url,
                resource_type="stylesheet",
                source_url=source_url
            ))

        # Extract scripts (script src)
        for script_tag in soup.select("script[src]"):
            src = script_tag.get("src", "")
            if not src:
                continue
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
        Uses a more efficient crawling strategy with better parallelism.

        Returns:
            Dict[str, List[Resource]]: Dictionary mapping resource types to lists of broken resources
        """
        # Reset performance metrics
        self.crawl_start_time = time.time()
        self.crawl_end_time = None
        self.url_processing_times = {}
        self.fetch_times = {}
        self.extraction_times = {}
        self.resource_check_times = {}
        self.total_requests = 0

        # Add the base URL to the queue
        self.queued_urls.add(self.base_url)

        # Track URL depths for BFS crawling
        url_depths = {self.base_url: 0}

        # Process URLs up to max_depth using a more efficient approach
        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit the initial URL
            future_to_url = {
                executor.submit(self._process_url_improved, self.base_url, 0): self.base_url
            }

            # Mark the initial URL as visited
            self.visited_urls.add(self.base_url)

            # Process URLs as they complete
            while future_to_url:
                # Wait for the next URL to complete
                done, _ = concurrent.futures.wait(
                    future_to_url, 
                    return_when=concurrent.futures.FIRST_COMPLETED
                )

                # Process completed URLs
                for future in done:
                    url = future_to_url.pop(future)
                    depth = url_depths[url]

                    try:
                        # Get new URLs discovered by this URL
                        new_urls = future.result()

                        # Only process new URLs if we haven't reached max depth
                        if depth < self.max_depth:
                            # Submit new URLs for processing
                            for new_url in new_urls:
                                if new_url not in self.visited_urls and new_url not in url_depths:
                                    # Mark URL as visited and track its depth
                                    self.visited_urls.add(new_url)
                                    url_depths[new_url] = depth + 1

                                    # Submit URL for processing
                                    future_obj = executor.submit(
                                        self._process_url_improved, new_url, depth + 1
                                    )
                                    future_to_url[future_obj] = new_url

                                    # Log progress
                                    logger.info(
                                        f"Queued URL: {new_url} (depth: {depth + 1}/{self.max_depth})"
                                    )
                    except Exception as e:
                        logger.error(f"Error processing URL {url}: {e}")

        # Record end time
        self.crawl_end_time = time.time()

        # Log performance summary
        total_time = self.crawl_end_time - self.crawl_start_time
        urls_per_second = len(self.visited_urls) / total_time if total_time > 0 else 0
        requests_per_second = self.total_requests / total_time if total_time > 0 else 0

        logger.info(f"Crawl completed in {total_time:.2f}s")
        logger.info(f"Processed {len(self.visited_urls)} URLs ({urls_per_second:.2f} URLs/s)")
        logger.info(f"Made {self.total_requests} requests ({requests_per_second:.2f} requests/s)")

        # Return the broken resources grouped by type
        return self._group_broken_resources()

    def _process_url_improved(self, url: str, depth: int) -> Set[str]:
        """
        Process a single URL: fetch it, extract resources, and check them.
        Returns a set of new URLs discovered.

        Args:
            url: URL to process
            depth: Current crawl depth

        Returns:
            Set[str]: Set of new URLs discovered
        """
        logger.info(f"Processing URL: {url} (depth: {depth}/{self.max_depth})")
        new_urls = set()

        url_start_time = time.time()

        # Fetch the URL
        fetch_start_time = time.time()
        html, status_code, error = self.fetch_url(url)
        fetch_end_time = time.time()

        # Track fetch time
        fetch_time = fetch_end_time - fetch_start_time
        self.fetch_times[url] = fetch_time
        self.total_requests += 1

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

            # Track total processing time for this URL
            url_end_time = time.time()
            self.url_processing_times[url] = url_end_time - url_start_time

            return new_urls

        # Extract resources from the HTML
        extraction_start_time = time.time()
        resources = self.extract_resources(html, url)
        extraction_end_time = time.time()

        # Track extraction time
        extraction_time = extraction_end_time - extraction_start_time
        self.extraction_times[url] = extraction_time
        logger.debug(f"Resource extraction for {url} took {extraction_time:.2f}s")

        # Check each resource in parallel
        resource_check_start_time = time.time()
        resource_check_count = 0

        with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
            # Submit all resource checks
            future_to_resource = {
                executor.submit(self.check_resource, resource): resource 
                for resource in resources
            }

            # Process results as they complete
            for future in concurrent.futures.as_completed(future_to_resource):
                resource = future_to_resource[future]
                try:
                    checked_resource = future.result()
                    self.all_resources[checked_resource.url] = checked_resource
                    resource_check_count += 1
                    self.total_requests += 1

                    if checked_resource.is_broken:
                        self.broken_resources.append(checked_resource)
                    elif checked_resource.resource_type == "link":
                        # Only add links to the new URLs if they're valid
                        if self.is_valid_url(checked_resource.url):
                            new_urls.add(checked_resource.url)
                except Exception as e:
                    logger.error(f"Error checking resource {resource.url}: {e}")

        # Track resource check time
        resource_check_end_time = time.time()
        resource_check_time = resource_check_end_time - resource_check_start_time
        if resource_check_count > 0:
            self.resource_check_times[url] = resource_check_time / resource_check_count  # Average time per resource

        # Track total processing time for this URL
        url_end_time = time.time()
        total_time = url_end_time - url_start_time
        self.url_processing_times[url] = total_time
        logger.debug(f"Total processing for {url} took {total_time:.2f}s")

        return new_urls

    def _process_url(self, url: str, depth: int) -> None:
        """
        Process a single URL: fetch it, extract resources, and check them.
        Legacy method kept for backward compatibility.

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

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get statistics about the crawl, including performance metrics.

        Returns:
            Dict[str, Any]: Dictionary of statistics and performance metrics
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

        # Basic statistics
        stats = {
            "total_urls_crawled": len(self.visited_urls),
            "total_resources": total_resources,
            "broken_resources": broken_count,
            "broken_percentage": (broken_count / total_resources * 100) if total_resources > 0 else 0,
            "resource_types": resource_types,
            "broken_by_type": broken_by_type
        }

        # Performance metrics
        if self.crawl_start_time and self.crawl_end_time:
            total_time = self.crawl_end_time - self.crawl_start_time

            # Calculate average times
            avg_url_time = sum(self.url_processing_times.values()) / len(self.url_processing_times) if self.url_processing_times else 0
            avg_fetch_time = sum(self.fetch_times.values()) / len(self.fetch_times) if self.fetch_times else 0
            avg_extraction_time = sum(self.extraction_times.values()) / len(self.extraction_times) if self.extraction_times else 0
            avg_resource_check_time = sum(self.resource_check_times.values()) / len(self.resource_check_times) if self.resource_check_times else 0

            # Calculate rates
            urls_per_second = len(self.visited_urls) / total_time if total_time > 0 else 0
            requests_per_second = self.total_requests / total_time if total_time > 0 else 0

            # Add performance metrics to statistics
            stats["performance"] = {
                "total_time": round(total_time, 2),  # Total crawl time in seconds
                "total_requests": self.total_requests,
                "urls_per_second": round(urls_per_second, 2),
                "requests_per_second": round(requests_per_second, 2),
                "avg_url_processing_time": round(avg_url_time, 3),  # Average time to process a URL in seconds
                "avg_fetch_time": round(avg_fetch_time, 3),  # Average time to fetch a URL in seconds
                "avg_extraction_time": round(avg_extraction_time, 3),  # Average time to extract resources in seconds
                "avg_resource_check_time": round(avg_resource_check_time, 3)  # Average time to check a resource in seconds
            }

        return stats
