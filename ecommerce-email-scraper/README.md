# E-commerce Store Email Scraper

Scrapes email addresses from e-commerce store websites (US & Europe) and exports them to Excel with the store URL.

## Quick Start

```bash
# 1. Create virtual environment and install dependencies
cd ecommerce-email-scraper
python3 -m venv venv
source venv/bin/activate   # On Windows: venv\Scripts\activate
pip install -r requirements.txt

# 2. Create a file with store URLs (one per line)
# stores.txt:
# https://www.example-store.com
# https://another-store.com

# 3. Run the scraper
python scraper.py stores.txt -o store_emails.xlsx
```

## Output

Creates an Excel file with columns:
| Store URL | Email(s) | Email Count |
|-----------|----------|-------------|
| https://store1.com | support@store1.com, hello@store1.com | 2 |
| https://store2.com | contact@store2.com | 1 |

## Getting the Store List

**The scraper needs a list of store URLs.** Here are ways to build it:

### Option 1: DuckDuckGo Search (FREE, no API key) ⭐
Use the included script to discover stores by category and region:

```bash
pip install ddgs   # if not already installed
python fetch_stores_duckduckgo.py -o discovered_stores.txt -r us uk germany france
python scraper.py discovered_stores.txt -o store_emails.xlsx
```

Searches 10 e-commerce categories across US, UK, Germany, France, etc. No signup, no limits (within reasonable use).

### Option 2: Manual List
Create `stores.txt` with one URL per line. Add stores you discover from:
- Your existing customer/supplier list
- Trade shows, industry directories
- Competitor research

### Option 3: Paid SERP APIs (when you need Google specifically)
- **Serpstack** – 100 free searches/month
- **Serpshot** – 2,000 free credits for new accounts
- **Searlo** – 3,000 free credits/month
- **SerpApi** – Free credits on signup

### Option 4: Paid E-commerce Directories (Recommended for Scale)
- **[StoreCensus](https://www.storecensus.com)** – 2.8M+ Shopify stores, filter by US/Europe, revenue, industry
- **[SellerDirectories](https://sellerdirectories.com)** – 40,000+ US Shopify stores with verified contacts
- **[BuiltWith](https://builtwith.com)** – E-commerce technology detection, export store lists

### Option 5: Google Custom Search API
**Note:** Closed to new customers as of 2024; discontinues Jan 2027. Was 100 queries/day free.

### Option 6: Scrape Store Directories
Some public directories list stores. **Important:** Always check `robots.txt` and Terms of Service before scraping. Many directories prohibit automated access.

### Option 7: Industry-Specific Sources
- Trade association member directories
- E-commerce platform partner lists (Shopify App Store, WooCommerce extensions)
- "Top 100" lists in your niche

## Usage

```bash
# From file
python scraper.py stores.txt

# Custom output file
python scraper.py stores.txt -o my_contacts.xlsx

# Comma-separated URLs (for quick testing)
python scraper.py "https://store1.com,https://store2.com"

# Slower scraping (more polite, fewer blocks)
python scraper.py stores.txt -d 5
```

## How It Works

1. **Visits each store** – Homepage + common contact pages (`/contact`, `/about`, `/contact-us`)
2. **Extracts emails** – Regex pattern + `mailto:` link parsing
3. **Filters noise** – Excludes common false positives (social media, CDNs, placeholder domains)
4. **Exports to Excel** – Clean spreadsheet with URL and email columns

## Legal & Ethical Considerations

⚠️ **Important:**
- **Respect robots.txt** – The scraper uses reasonable delays (2 sec default)
- **Terms of Service** – Many sites prohibit scraping; review before large-scale use
- **GDPR/CCPA** – If you're in EU or California, ensure your use of scraped emails complies with privacy laws
- **CAN-SPAM** – Only email contacts who have opted in or where you have legitimate interest
- **Rate limiting** – Use `-d 5` or higher for large lists to avoid overloading servers

## Requirements

- Python 3.8+
- Dependencies in `requirements.txt`

## Troubleshooting

| Issue | Solution |
|-------|----------|
| No emails found | Many stores hide emails; try contact forms only |
| Blocked/403 errors | Increase delay (`-d 5`), use proxies for large runs |
| Timeout errors | Some sites are slow; the scraper will skip and continue |
| Invalid emails | Review `EXCLUDED_EMAIL_DOMAINS` in scraper.py if legitimate emails are filtered |
