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
| `SENT_COOLDOWN_DAYS` | No | Don’t email the same address (or same canonical store URL) again within this many days (default **90**). Set lower only for testing. |
| `LIST_UNSUBSCRIBE_MAILTO` | No | Optional `mailto:…` for the `List-Unsubscribe` header (defaults to `mailto:FROM_EMAIL?subject=unsubscribe`) |

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

4. **Deduplication**
   - The workflow restores and **re-saves** `data/sent_stores.json` via Actions cache each run so the log actually updates (a plain cache “hit” used to skip uploading, so recipients could get mail every day).
   - Sends are keyed by **recipient email** and **normalized store URL**, with cooldown from `SENT_COOLDOWN_DAYS`.

---

## Inbox placement (not “spam”)

Cold outreach to scraped addresses is inherently risky. To improve delivery:

1. **DNS** – Complete Resend’s SPF + DKIM (and ideally **DMARC** on your domain). `FROM_EMAIL` must match the verified domain.
2. **One mail per address** – Keep `SENT_COOLDOWN_DAYS` high (90+); avoid daily repeats to the same inbox.
3. **Content** – A clear **plain-text** part, a **specific** subject (store hostname + context), and a truthful footer help more than all-caps “FREE AUDIT”.
4. **Reputation** – Warm the domain, send in low volume, and stop addresses that bounce or mark spam.

---

## Resend Setup (Required for sending to brands)

**403 Forbidden?** Resend's `onboarding@resend.dev` can only send to your own email. To send to scraped store emails, you must verify your domain.

1. Sign up at [resend.com](https://resend.com)
2. **Verify your domain** at [resend.com/domains](https://resend.com/domains):
   - Add domain (e.g. `sellonllm.com`)
   - Add the DNS records (SPF, DKIM) they provide
   - Wait for verification
3. Create an API key: **API Keys → Create**
4. Set `FROM_EMAIL` to your verified address (e.g. `audit@sellonllm.com`)
5. Add `RESEND_API_KEY` as a GitHub secret

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

- By default, the same **recipient email** or **canonical store URL** is not emailed again within `SENT_COOLDOWN_DAYS` (**90** by default).
- Sent log: `ecommerce-email-scraper/data/sent_stores.json` (fields `by_email`, `by_url`).
- Use `--no-skip-sent` to ignore the log (testing only).

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
