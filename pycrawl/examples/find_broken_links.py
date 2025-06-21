#!/usr/bin/env python
"""
Example script that demonstrates how to use the BrokenLinkChecker to find broken links on a website.
"""
import argparse
import sys
import logging
from pycrawl.crawler import BrokenLinkChecker

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("pycrawl-example")


def main():
    """Main function that parses arguments and runs the crawler."""
    parser = argparse.ArgumentParser(
        description="Find broken links and resources on a website."
    )
    parser.add_argument(
        "url",
        help="The URL to crawl (e.g., https://example.com)"
    )
    parser.add_argument(
        "--depth",
        type=int,
        default=2,
        help="Maximum crawl depth (default: 2)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=10,
        help="Maximum number of concurrent workers (default: 10)"
    )
    parser.add_argument(
        "--timeout",
        type=int,
        default=10,
        help="Timeout for HTTP requests in seconds (default: 10)"
    )
    parser.add_argument(
        "--user-agent",
        default="PyCrawl/0.1.0",
        help="User agent string to use for requests (default: PyCrawl/0.1.0)"
    )
    parser.add_argument(
        "--output",
        help="Output file for the report (default: stdout)"
    )
    parser.add_argument(
        "--username",
        help="Username for HTTP Basic Authentication"
    )
    parser.add_argument(
        "--password",
        help="Password for HTTP Basic Authentication"
    )

    args = parser.parse_args()

    try:
        # Create the crawler
        logger.info(f"Starting crawler for {args.url} with depth {args.depth}")

        # Set up auth if provided
        auth = None
        if args.username and args.password:
            auth = (args.username, args.password)
            logger.info("Using HTTP Basic Authentication")

        checker = BrokenLinkChecker(
            base_url=args.url,
            max_depth=args.depth,
            max_workers=args.workers,
            timeout=args.timeout,
            user_agent=args.user_agent,
            auth=auth
        )

        # Start crawling
        logger.info("Crawling started...")
        broken_resources = checker.crawl()

        # Generate report
        report = checker.generate_report()

        # Output report
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)
            logger.info(f"Report written to {args.output}")
        else:
            print("\n" + report)

        # Print statistics
        stats = checker.get_statistics()
        print("\nCrawl Statistics:")
        print(f"Total URLs crawled: {stats['total_urls_crawled']}")
        print(f"Total resources checked: {stats['total_resources']}")
        print(f"Broken resources: {stats['broken_resources']} ({stats['broken_percentage']:.1f}%)")

        # Print broken resources by type
        if stats['broken_by_type']:
            print("\nBroken resources by type:")
            for resource_type, count in stats['broken_by_type'].items():
                print(f"  {resource_type}: {count}")

        # Return non-zero exit code if broken links were found
        if stats['broken_resources'] > 0:
            return 1
        return 0

    except Exception as e:
        logger.error(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
