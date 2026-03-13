#!/usr/bin/env python3
"""
Helper script to prepare store lists for the email scraper.
Converts various input formats to the standard URL-per-line format.
"""

import csv
import json
import sys
from pathlib import Path


def extract_urls_from_csv(filepath: str, url_column: str = None) -> list:
    """
    Extract URLs from a CSV file.
    Auto-detects URL column if not specified (looks for 'url', 'website', 'store', 'domain').
    """
    urls = []
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames or []
        
        # Find URL column
        url_col = url_column
        if not url_col:
            for h in headers:
                if h.lower() in ('url', 'website', 'store', 'domain', 'link', 'site'):
                    url_col = h
                    break
            if not url_col and headers:
                url_col = headers[0]  # Fallback to first column
        
        for row in reader:
            url = row.get(url_col, '').strip()
            if url and ('http' in url or '.' in url):
                if not url.startswith(('http://', 'https://')):
                    url = 'https://' + url
                urls.append(url)
    
    return urls


def extract_urls_from_json(filepath: str, url_key: str = 'url') -> list:
    """Extract URLs from a JSON file (array of objects or object with URLs array)."""
    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    urls = []
    if isinstance(data, list):
        for item in data:
            if isinstance(item, dict):
                url = item.get(url_key) or item.get('website') or item.get('domain') or item.get('store')
                if url:
                    urls.append(url if url.startswith('http') else 'https://' + url)
            elif isinstance(item, str) and ('http' in item or '.' in item):
                urls.append(item if item.startswith('http') else 'https://' + item)
    elif isinstance(data, dict):
        for key in ('urls', 'stores', 'websites', 'domains'):
            if key in data and isinstance(data[key], list):
                for url in data[key]:
                    if url:
                        urls.append(url if str(url).startswith('http') else 'https://' + str(url))
                break
    
    return urls


def extract_urls_from_text(filepath: str) -> list:
    """Extract URLs from plain text (one per line)."""
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        return [
            (line.strip() if line.strip().startswith('http') else 'https://' + line.strip())
            for line in f
            if line.strip() and not line.strip().startswith('#')
        ]


def convert_to_scraper_format(input_path: str, output_path: str = None, url_column: str = None):
    """
    Convert various file formats to scraper-ready format (one URL per line).
    """
    path = Path(input_path)
    if not path.exists():
        print(f"Error: File not found: {input_path}")
        return []
    
    suffix = path.suffix.lower()
    
    if suffix == '.csv':
        urls = extract_urls_from_csv(str(path), url_column)
    elif suffix == '.json':
        urls = extract_urls_from_json(str(path))
    else:
        urls = extract_urls_from_text(str(path))
    
    # Deduplicate while preserving order
    seen = set()
    unique_urls = []
    for u in urls:
        normalized = u.lower().rstrip('/')
        if normalized not in seen:
            seen.add(normalized)
            unique_urls.append(u)
    
    if output_path:
        with open(output_path, 'w') as f:
            f.write('\n'.join(unique_urls))
        print(f"Wrote {len(unique_urls)} URLs to {output_path}")
    else:
        for u in unique_urls:
            print(u)
    
    return unique_urls


def main():
    import argparse
    parser = argparse.ArgumentParser(description='Convert store lists to scraper format')
    parser.add_argument('input', help='Input file (CSV, JSON, or TXT)')
    parser.add_argument('-o', '--output', help='Output file (default: print to stdout)')
    parser.add_argument('--url-column', help='CSV column name containing URLs')
    args = parser.parse_args()
    
    convert_to_scraper_format(args.input, args.output, args.url_column)


if __name__ == '__main__':
    main()
