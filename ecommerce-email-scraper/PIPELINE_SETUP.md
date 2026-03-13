# Daily LLM Audit Pipeline – Setup Guide

Automated flow that runs **every day**:

1. **DuckDuckGo** – Discover e-commerce store URLs (US, UK, Europe)
2. **Email scrape** – Extract contact emails from each store
3. **LLM audit** – Run SellOnLLM audit API for each store
4. **Email report** – Send the audit report to each store’s email

---

## Quick Start (Local)

```bash
cd ecommerce-email-scraper
source venv/bin/activate  # or: venv\Scripts\activate on Windows
pip install -r requirements.txt

# Quick test with 1 store (skip DuckDuckGo, use sample_stores.txt)
python daily_pipeline.py --urls-file sample_stores.txt --max 1

# Dry run (no emails sent)
python daily_pipeline.py --dry-run --max 3

# Full run (requires RESEND_API_KEY)
export RESEND_API_KEY=re_xxxxx
export SUMMARY_EMAIL=you@gmail.com   # Daily summary sent here
python daily_pipeline.py
```

---

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `RESEND_API_KEY` | Yes (for email) | Resend API key. Get free at [resend.com](https://resend.com) (3,000 emails/month free) |
| `FROM_EMAIL` | No | Sender email (default: `audit@sellonllm.com`). Must be verified in Resend |
| `SENDER_NAME` | No | Display name shown to recipients (e.g. `SellOnLLM` or `Vipul from SellOnLLM`) |
| `SUMMARY_EMAIL` | No | Your Gmail (or any email) to receive the daily summary: URLs scraped, emails found, reports generated, emails sent |

---

## GitHub Actions (Daily Automation)

1. **Add secrets** in GitHub repo: **Settings → Secrets and variables → Actions**
   - `RESEND_API_KEY`: Your Resend API key
   - `SUMMARY_EMAIL`: Your Gmail (e.g. `you@gmail.com`) – receives daily summary with URLs scraped, emails found, reports generated, emails sent

2. **Optional variables**
   - `FROM_EMAIL`: Custom sender (e.g. `audit@yourdomain.com`)

3. **Schedule**
   - Runs daily at **6:00 AM UTC** (configurable in `.github/workflows/daily-llm-audit.yml`)
   - Run manually: **Actions → Daily LLM Audit Pipeline → Run workflow**

---

## Resend Setup

1. Sign up at [resend.com](https://resend.com)
2. Verify your domain (or use their test domain for testing)
3. Create an API key: **API Keys → Create**
4. Add the key as `RESEND_API_KEY` in your environment or GitHub secrets

---

## Pipeline Options

```bash
# Regions to search
python daily_pipeline.py --regions us uk germany france

# Limit stores (for testing)
python daily_pipeline.py --max 5

# Re-email stores even if sent recently
python daily_pipeline.py --no-skip-sent

# Dry run – no emails sent
python daily_pipeline.py --dry-run
```

---

## Deduplication

- Stores that received an audit in the last **7 days** are skipped by default
- Sent log: `ecommerce-email-scraper/data/sent_stores.json`
- Use `--no-skip-sent` to override

---

## Customizing the Email Body

Edit the `audit_to_html()` function in `daily_pipeline.py` (around line 99). The HTML template includes:
- Audit score and check results
- Shopify app CTA: [apps.shopify.com/llm-analytics](https://apps.shopify.com/llm-analytics)
- Video call offer link: [sellonllm.com/contact-us.html](https://sellonllm.com/contact-us.html)

---

## Output

- `data/store_emails.xlsx` – Store URLs and scraped emails
- `data/sent_stores.json` – Stores that received audit emails (with dates)
