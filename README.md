# AutoEmailer – Daily LLM Audit Pipeline

Automated pipeline that discovers e-commerce stores, scrapes emails, runs LLM audits, and emails reports to brands.

## Flow

1. **DuckDuckGo** – Discover store URLs (US, UK, Europe)
2. **Email scrape** – Extract contact emails from stores
3. **LLM audit** – Run SellOnLLM audit for each store
4. **Email report** – Send audit report (only when successful)

## Setup

See [ecommerce-email-scraper/PIPELINE_SETUP.md](ecommerce-email-scraper/PIPELINE_SETUP.md) and [ecommerce-email-scraper/GITHUB_SETUP.md](ecommerce-email-scraper/GITHUB_SETUP.md).

## GitHub Secrets

- `RESEND_API_KEY` – Resend API key
- `SUMMARY_EMAIL` – Your email for daily summary

## Schedule

Runs daily at 6:00 AM UTC via GitHub Actions.
