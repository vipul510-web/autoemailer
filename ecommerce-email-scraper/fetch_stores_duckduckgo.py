#!/usr/bin/env python3
"""
Fetch e-commerce store URLs using DuckDuckGo Search - 100% FREE, no API key required.
Uses the duckduckgo-search Python library to discover stores by category and region.
"""

import time
from pathlib import Path

# E-commerce categories to search (customize as needed)
ECOM_CATEGORIES = [
    "fashion clothing online store",
    "beauty cosmetics ecommerce shop",
    "home decor furniture store",
    "electronics gadgets online shop",
    "sports outdoor gear store",
    "jewelry accessories ecommerce",
    "food snacks subscription box",
    "pet supplies online store",
    "baby kids products shop",
    "health wellness ecommerce",
]

# Region codes: us-en (US), uk-en (UK), de-de (Germany), fr-fr (France), etc.
REGIONS = {
    "us": "us-en",
    "uk": "uk-en",
    "germany": "de-de",
    "france": "fr-fr",
    "italy": "it-it",
    "spain": "es-es",
    "netherlands": "nl-nl",
}


def fetch_store_urls(
    categories: list = None,
    regions: list = None,
    max_results_per_query: int = 30,
    delay_between_queries: float = 2.0,
) -> list[str]:
    """
    Search DuckDuckGo for e-commerce stores and return unique URLs.
    No API key needed - uses the free duckduckgo-search library.
    """
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            print("Install: pip install ddgs  (or pip install duckduckgo-search)")
            return []

    categories = categories or ECOM_CATEGORIES
    regions = regions or ["us", "uk"]
    seen_urls = set()
    all_urls = []

    ddgs = DDGS()

    for region_key in regions:
        region = REGIONS.get(region_key, "us-en")
        print(f"\nSearching region: {region} ({region_key})")

        for category in categories:
            query = f"{category} buy shop"
            print(f"  Query: {query[:50]}...")

            try:
                results = list(
                    ddgs.text(
                        query,
                        region=region,
                        max_results=max_results_per_query,
                    )
                )

                for r in results:
                    url = r.get("href") or r.get("url", "")
                    if url and url not in seen_urls:
                        # Filter to likely store domains (exclude Wikipedia, etc.)
                        skip = any(
                            x in url.lower()
                            for x in [
                                "wikipedia.org",
                                "facebook.com",
                                "twitter.com",
                                "linkedin.com",
                                "youtube.com",
                                "pinterest.com",
                                "instagram.com",
                                "amazon.com",
                                "ebay.com",
                                "walmart.com",
                                "target.com",
                                "reddit.com",
                                "quora.com",
                            ]
                        )
                        if not skip:
                            seen_urls.add(url)
                            all_urls.append(url)

                time.sleep(delay_between_queries)

            except Exception as e:
                print(f"  Error: {e}")
                # DuckDuckGo may rate-limit; wait and retry
                time.sleep(5)

    return all_urls


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="Fetch e-commerce store URLs via DuckDuckGo (free, no API key)"
    )
    parser.add_argument(
        "-o", "--output",
        default="discovered_stores.txt",
        help="Output file for store URLs",
    )
    parser.add_argument(
        "-r", "--regions",
        nargs="+",
        default=["us", "uk"],
        choices=list(REGIONS.keys()),
        help="Regions to search (default: us uk)",
    )
    parser.add_argument(
        "-m", "--max",
        type=int,
        default=30,
        help="Max results per search query (default: 30)",
    )
    parser.add_argument(
        "-d", "--delay",
        type=float,
        default=2.0,
        help="Delay between queries in seconds (default: 2)",
    )

    args = parser.parse_args()

    print("Fetching store URLs via DuckDuckGo (free, no API key)...")
    urls = fetch_store_urls(
        regions=args.regions,
        max_results_per_query=args.max,
        delay_between_queries=args.delay,
    )

    # Save to file
    Path(args.output).write_text("\n".join(urls), encoding="utf-8")
    print(f"\nSaved {len(urls)} unique store URLs to {args.output}")
    print("Run: python scraper.py", args.output, "-o store_emails.xlsx")


if __name__ == "__main__":
    main()
