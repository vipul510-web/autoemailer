#!/usr/bin/env python3
"""
E-commerce Store Email Scraper
Scrapes email addresses from e-commerce store websites and exports to Excel.
"""

import re
import time
import urllib.parse
from pathlib import Path

import pandas as pd
import requests
from bs4 import BeautifulSoup
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter

# Email regex - matches common email patterns
EMAIL_REGEX = re.compile(
    r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'
)

# Domains to exclude (common false positives in HTML)
EXCLUDED_EMAIL_DOMAINS = {
    'example.com', 'example.org', 'test.com', 'email.com',
    'domain.com', 'sentry.io', 'wixpress.com', 'schema.org',
    'w3.org', 'placeholder.com', 'yoursite.com', 'yourdomain.com',
    'cdn.jsdelivr.net', 'fonts.googleapis.com', 'gravatar.com',
    'facebook.com', 'twitter.com', 'instagram.com', 'linkedin.com',
    'youtube.com', 'pinterest.com', 'tiktok.com', 'snapchat.com',
    'google.com', 'googleapis.com', 'gstatic.com', 'gmail.com',
    'yahoo.com', 'hotmail.com', 'outlook.com', 'live.com',
    'cloudflare.com', 'amazonaws.com', 'shopify.com', 'myshopify.com',
}


def create_session():
    """Create a requests session with retries and proper headers."""
    session = requests.Session()
    retries = Retry(total=3, backoff_factor=1, status_forcelist=[500, 502, 503, 504])
    session.mount('https://', HTTPAdapter(max_retries=retries))
    session.mount('http://', HTTPAdapter(max_retries=retries))
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.5',
    })
    return session


def is_valid_email(email: str) -> bool:
    """Validate email - check domain and TLD are reasonable."""
    try:
        local, domain = email.lower().rsplit('@', 1)
        if domain in EXCLUDED_EMAIL_DOMAINS:
            return False
        if any(domain.endswith(ext) for ext in ('.png', '.jpg', '.gif', '.svg', '.webp')):
            return False
        # Reject concatenated false positives (e.g. "domain.comcareers", "site.compress")
        if re.search(r'\.(com|org|net)[a-z]+$', domain):
            return False
        return True
    except (ValueError, IndexError):
        return False


def extract_emails_from_text(text: str) -> set:
    """Extract valid email addresses from text, filtering out common false positives."""
    if not text:
        return set()
    
    emails = set()
    for match in EMAIL_REGEX.finditer(text):
        email = match.group().lower()
        if is_valid_email(email):
            emails.add(email)
    return emails


def get_store_emails(url: str, session: requests.Session, max_pages: int = 5) -> set:
    """
    Scrape a store URL and common subpages for email addresses.
    Checks: homepage, /contact, /about, /about-us, /contact-us, /pages/contact
    """
    all_emails = set()
    base_domain = urllib.parse.urlparse(url).netloc
    
    # Normalize URL
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
    
    pages_to_check = [
        url,
        url.rstrip('/') + '/contact',
        url.rstrip('/') + '/about',
        url.rstrip('/') + '/about-us',
        url.rstrip('/') + '/contact-us',
        url.rstrip('/') + '/pages/contact',
        url.rstrip('/') + '/pages/about',
    ]
    
    for i, page_url in enumerate(pages_to_check[:max_pages]):
        try:
            response = session.get(page_url, timeout=15, allow_redirects=True)
            response.raise_for_status()
            
            if 'text/html' not in response.headers.get('Content-Type', ''):
                continue
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Remove script and style elements
            for element in soup(['script', 'style']):
                element.decompose()
            
            # Get text content
            text = soup.get_text()
            
            # Also check mailto links
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if href.startswith('mailto:'):
                    email = href.replace('mailto:', '').split('?')[0].strip().lower()
                    if '@' in email and EMAIL_REGEX.match(email):
                        all_emails.add(email)
            
            # Check data attributes and JSON-LD
            page_html = str(soup)
            all_emails.update(extract_emails_from_text(text))
            all_emails.update(extract_emails_from_text(page_html))
            
        except requests.RequestException as e:
            if i == 0:  # Only log first page failure
                print(f"  Warning: Could not fetch {page_url}: {e}")
            continue
        except Exception as e:
            if i == 0:
                print(f"  Warning: Error parsing {page_url}: {e}")
            continue
        
        time.sleep(1)  # Be respectful - rate limiting
    
    return all_emails


def get_store_list_from_file(filepath: str) -> list:
    """Load store URLs from a text file (one URL per line)."""
    with open(filepath, 'r') as f:
        return [line.strip() for line in f if line.strip() and not line.startswith('#')]


def scrape_stores(
    store_urls: list,
    output_file: str = 'store_emails.xlsx',
    delay_between_stores: float = 2.0
) -> pd.DataFrame:
    """
    Scrape all stores and return results as DataFrame.
    """
    results = []
    session = create_session()
    total = len(store_urls)
    
    print(f"Starting scrape of {total} stores...")
    print("-" * 50)
    
    for i, url in enumerate(store_urls, 1):
        url = url.strip()
        if not url:
            continue
            
        print(f"[{i}/{total}] Scraping: {url}")
        
        try:
            emails = get_store_emails(url, session)
            email_str = ', '.join(sorted(emails)) if emails else ''
            results.append({
                'Store URL': url,
                'Email(s)': email_str,
                'Email Count': len(emails)
            })
            print(f"  Found {len(emails)} email(s): {email_str or 'None'}")
        except Exception as e:
            print(f"  Error: {e}")
            results.append({
                'Store URL': url,
                'Email(s)': '',
                'Email Count': 0
            })
        
        if i < total:
            time.sleep(delay_between_stores)
    
    df = pd.DataFrame(results)
    
    # Save to Excel
    df.to_excel(output_file, index=False, sheet_name='Store Emails')
    print("-" * 50)
    print(f"Done! Results saved to {output_file}")
    print(f"Total stores scraped: {len(results)}")
    print(f"Stores with emails: {sum(1 for r in results if r['Email Count'] > 0)}")
    
    return df


def main():
    import argparse
    
    parser = argparse.ArgumentParser(description='Scrape emails from e-commerce stores')
    parser.add_argument(
        'input',
        nargs='?',
        help='Input: path to text file with store URLs (one per line) OR comma-separated URLs'
    )
    parser.add_argument(
        '-o', '--output',
        default='store_emails.xlsx',
        help='Output Excel file path (default: store_emails.xlsx)'
    )
    parser.add_argument(
        '-d', '--delay',
        type=float,
        default=2.0,
        help='Delay between store requests in seconds (default: 2.0)'
    )
    
    args = parser.parse_args()
    
    if args.input:
        # Check if it's a file path
        if Path(args.input).is_file():
            store_urls = get_store_list_from_file(args.input)
        else:
            # Treat as comma-separated URLs
            store_urls = [u.strip() for u in args.input.split(',') if u.strip()]
    else:
        # Use sample stores for demo
        sample_file = Path(__file__).parent / 'sample_stores.txt'
        if sample_file.exists():
            store_urls = get_store_list_from_file(str(sample_file))
            print("Using sample_stores.txt (provide input file or URLs for full run)")
        else:
            print("Error: No input provided. Usage:")
            print("  python scraper.py stores.txt -o output.xlsx")
            print("  python scraper.py 'https://store1.com,https://store2.com'")
            return
    
    if not store_urls:
        print("No store URLs to scrape.")
        return
    
    scrape_stores(store_urls, args.output, args.delay)


if __name__ == '__main__':
    main()
