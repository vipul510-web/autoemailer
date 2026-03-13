#!/usr/bin/env python3
"""
Daily automated pipeline:
1. DuckDuckGo: Discover e-commerce store URLs
2. Scrape emails from stores
3. For each store with email: Run LLM audit, generate report, email it

Run daily via cron or GitHub Actions.
"""

import json
import os
import time
from datetime import datetime
from pathlib import Path

import requests

# Paths
SCRIPT_DIR = Path(__file__).parent
DATA_DIR = SCRIPT_DIR / "data"
SENT_LOG = DATA_DIR / "sent_stores.json"
AUDIT_API = "https://sellonllm.com/api/audit-site"

# Check names for display
CHECK_LABELS = {
    "llm_txt_exists": "LLM.txt",
    "robots_txt_proper": "Robots.txt",
    "sitemap_exists": "Sitemap",
    "ssl_enabled": "SSL/HTTPS",
    "meta_titles_present": "Meta Titles",
    "meta_descriptions_present": "Meta Descriptions",
    "content_quality": "Content Quality",
    "structured_data_basic": "Structured Data",
    "mobile_friendly": "Mobile Friendly",
    "open_graph_tags": "Open Graph",
    "twitter_cards": "Twitter Cards",
    "image_optimization": "Image Optimization",
}


def load_sent_log():
    """Load store URLs we've already sent audits to."""
    if SENT_LOG.exists():
        with open(SENT_LOG) as f:
            return json.load(f)
    return {}


def save_sent_log(data):
    """Save sent log."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(SENT_LOG, "w") as f:
        json.dump(data, f, indent=2)


def run_duckduckgo_discovery(regions=None, max_per_query=25):
    """Discover store URLs via DuckDuckGo."""
    from fetch_stores_duckduckgo import fetch_store_urls

    regions = regions or ["us", "uk"]
    urls = fetch_store_urls(
        regions=regions,
        max_results_per_query=max_per_query,
        delay_between_queries=1.5,
    )
    return urls


def run_email_scraper(store_urls, delay=1.5):
    """Scrape emails from stores. Returns list of dicts with Store URL, Email(s), Email Count."""
    from scraper import scrape_stores

    output_file = DATA_DIR / "store_emails.xlsx"
    DATA_DIR.mkdir(exist_ok=True)
    df = scrape_stores(
        store_urls,
        output_file=str(output_file),
        delay_between_stores=delay,
    )
    return df.to_dict("records")


def run_audit(store_url):
    """Call SellOnLLM audit API and return JSON result."""
    try:
        resp = requests.post(
            AUDIT_API,
            json={"url": store_url, "maxPages": 20},
            headers={"Content-Type": "application/json"},
            timeout=90,
        )
        resp.raise_for_status()
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


def get_audit_score(audit_data):
    """Extract overall score (0-100) from audit data. Returns None if audit failed."""
    if "error" in audit_data:
        return None
    summary = audit_data.get("summary", {})
    checks = summary.get("checks", {})
    total_checks = len(checks)
    if not total_checks:
        return 0
    passed = sum(1 for c in checks.values() if c.get("percentage", 0) >= 50)
    return round((passed / total_checks) * 100)


def audit_to_html(store_url, audit_data, recipient_email):
    """Convert audit JSON to HTML email body. Returns None if audit failed (do not send email)."""
    if "error" in audit_data:
        return None  # Don't send email when report generation fails

    summary = audit_data.get("summary", {})
    checks = summary.get("checks", {})

    # Overall score
    total_checks = len(checks)
    passed = sum(1 for c in checks.values() if c.get("percentage", 0) >= 50)
    overall_score = round((passed / total_checks) * 100) if total_checks else 0

    score_color = "#22c55e" if overall_score >= 70 else "#f59e0b" if overall_score >= 50 else "#ef4444"

    rows = []
    for key, data in checks.items():
        label = CHECK_LABELS.get(key, key.replace("_", " ").title())
        pct = data.get("percentage", 0)
        status = "✓" if pct >= 50 else "✗"
        color = "#22c55e" if pct >= 50 else "#ef4444"
        details = data.get("details", "—")[:200]
        rows.append(
            f"""
            <tr>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;">{status} {label}</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;color:{color};font-weight:600;">{pct}%</td>
                <td style="padding:8px;border-bottom:1px solid #e5e7eb;font-size:0.9em;">{details}</td>
            </tr>
            """
        )

    checks_table = "\n".join(rows)

    return f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>LLM Audit Report</title></head>
<body style="font-family:system-ui,-apple-system,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1f2937;">
    <div style="text-align:center;margin-bottom:24px;">
        <h1 style="color:#3b82f6;margin:0;">SellOnLLM</h1>
        <p style="color:#6b7280;margin:4px 0 0;">AI & SEO Readiness Audit</p>
    </div>

    <h2 style="font-size:1.25rem;">Here's Your Free LLM Audit Report</h2>
    <p>Hi,</p>
    <p>We analyzed <strong>{store_url}</strong> for AI discoverability (ChatGPT, Claude, Perplexity) and SEO readiness. Here are your results:</p>

    <div style="background:#f8fafc;border-radius:12px;padding:24px;text-align:center;margin:24px 0;">
        <div style="font-size:2.5rem;font-weight:800;color:{score_color};">{overall_score}/100</div>
        <div style="color:#64748b;margin-top:4px;">Overall Score</div>
    </div>

    <table style="width:100%;border-collapse:collapse;margin:24px 0;">
        <thead>
            <tr style="background:#f1f5f9;">
                <th style="padding:8px;text-align:left;">Check</th>
                <th style="padding:8px;width:60px;">Score</th>
                <th style="padding:8px;text-align:left;">Details</th>
            </tr>
        </thead>
        <tbody>
            {checks_table}
        </tbody>
    </table>

    <p style="margin-top:24px;">If you want more visibility on AI platforms like ChatGPT, you can also try our <a href="https://apps.shopify.com/llm-analytics" style="color:#3b82f6;">Shopify app</a> to create content that will help your store stand out on ChatGPT and other AI platforms.</p>
    <p><a href="https://apps.shopify.com/llm-analytics" style="display:inline-block;background:#3b82f6;color:white;padding:12px 24px;text-decoration:none;border-radius:8px;font-weight:600;">Try ChatGPT AEO App on Shopify →</a></p>

    <hr style="border:none;border-top:1px solid #e5e7eb;margin:32px 0;">
    <p style="font-size:0.85em;color:#6b7280;">
        You received this because we found your store in our e-commerce research. Unsubscribe by replying with "unsubscribe".
    </p>
    <p style="font-size:0.85em;color:#6b7280;">SellOnLLM · <a href="https://sellonllm.com">sellonllm.com</a></p>
</body>
</html>
"""


def send_email(to_email, subject, html_body):
    """Send email via Resend API."""
    api_key = os.environ.get("RESEND_API_KEY")
    from_email = os.environ.get("FROM_EMAIL", "audit@sellonllm.com")
    sender_name = os.environ.get("SENDER_NAME", "Vipul from SellOnLLM").strip()

    # Format: "Name <email>" or just "email" if no name
    from_field = f"{sender_name} <{from_email}>" if sender_name else from_email

    if not api_key:
        print("  [SKIP] RESEND_API_KEY not set - email not sent")
        return False

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "from": from_field,
                "to": [to_email],
                "subject": subject,
                "html": html_body,
            },
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except Exception as e:
        print(f"  [ERROR] Email failed: {e}")
        return False


def send_daily_summary(summary_email, stats):
    """Send daily pipeline summary to the configured email."""
    urls_scraped = stats.get("urls_scraped", 0)
    emails_found = stats.get("emails_found", 0)
    llm_reports_generated = stats.get("llm_reports_generated", 0)
    emails_sent = stats.get("emails_sent", 0)
    date_str = stats.get("date", datetime.now().strftime("%Y-%m-%d"))
    sample_urls = stats.get("sample_urls", [])[:30]

    url_list = "\n".join(f"  • {u}" for u in sample_urls) if sample_urls else "  (none)"
    if urls_scraped > len(sample_urls):
        url_list += f"\n  ... and {urls_scraped - len(sample_urls)} more"

    html = f"""
<!DOCTYPE html>
<html>
<head><meta charset="utf-8"><title>Daily Pipeline Summary</title></head>
<body style="font-family:system-ui,-apple-system,sans-serif;max-width:600px;margin:0 auto;padding:20px;color:#1f2937;">
    <h1 style="color:#3b82f6;">Daily LLM Audit Pipeline Summary</h1>
    <p style="color:#6b7280;">{date_str}</p>

    <table style="width:100%;border-collapse:collapse;margin:24px 0;">
        <tr style="background:#f8fafc;"><td style="padding:12px;font-weight:600;">URLs scraped</td><td style="padding:12px;text-align:right;font-size:1.25rem;">{urls_scraped}</td></tr>
        <tr><td style="padding:12px;font-weight:600;">Emails found</td><td style="padding:12px;text-align:right;font-size:1.25rem;">{emails_found}</td></tr>
        <tr style="background:#f8fafc;"><td style="padding:12px;font-weight:600;">LLM reports generated</td><td style="padding:12px;text-align:right;font-size:1.25rem;">{llm_reports_generated}</td></tr>
        <tr><td style="padding:12px;font-weight:600;">Emails sent</td><td style="padding:12px;text-align:right;font-size:1.25rem;color:#22c55e;">{emails_sent}</td></tr>
    </table>

    <h3 style="margin-top:24px;">Sample URLs discovered</h3>
    <pre style="background:#f1f5f9;padding:16px;border-radius:8px;font-size:0.85em;overflow-x:auto;">{url_list}</pre>

    <hr style="border:none;border-top:1px solid #e5e7eb;margin:24px 0;">
    <p style="font-size:0.85em;color:#6b7280;">SellOnLLM Daily Pipeline · sellonllm.com</p>
</body>
</html>
"""
    return send_email(summary_email, f"Daily Pipeline Summary – {date_str}", html)


def run_full_pipeline(
    regions=None,
    skip_sent=True,
    max_stores_with_emails=None,
    dry_run=False,
    urls_file=None,
):
    """
    Run the full daily pipeline.
    skip_sent: Don't re-email stores we've already sent to (within 7 days)
    max_stores_with_emails: Limit how many stores to process (for testing)
    dry_run: Don't send emails, just log what would happen
    urls_file: Skip DuckDuckGo and use URLs from this file (for quick testing)
    """
    DATA_DIR.mkdir(exist_ok=True)
    sent_log = load_sent_log()
    summary_email = os.environ.get("SUMMARY_EMAIL", "").strip()

    # Stats for daily summary
    stats = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "urls_scraped": 0,
        "emails_found": 0,
        "llm_reports_generated": 0,
        "emails_sent": 0,
        "sample_urls": [],
    }

    print("=" * 60)
    print("DAILY PIPELINE", datetime.now().isoformat())
    print("=" * 60)

    # Step 1: Discover stores (or load from file)
    if urls_file and Path(urls_file).exists():
        print(f"\n[1/4] Using URLs from {urls_file} (skip DuckDuckGo)...")
        with open(urls_file) as f:
            store_urls = [u.strip() for u in f if u.strip() and not u.startswith("#")]
    else:
        print("\n[1/4] Discovering stores via DuckDuckGo...")
        store_urls = run_duckduckgo_discovery(regions=regions or ["us", "uk"])

    stats["urls_scraped"] = len(store_urls)
    stats["sample_urls"] = store_urls.copy()
    print(f"  Found {len(store_urls)} store URLs")

    if not store_urls:
        print("No stores found. Exiting.")
        if summary_email:
            send_daily_summary(summary_email, stats)
        return

    # Step 2: Scrape emails
    print("\n[2/4] Scraping emails from stores...")
    store_data = run_email_scraper(store_urls, delay=1.5)
    stores_with_emails = [s for s in store_data if s["Email Count"] > 0]
    stats["emails_found"] = len(stores_with_emails)
    print(f"  {len(stores_with_emails)} stores have email addresses")

    # Resend free tier: 100 emails/day. Cap to stay within limit.
    max_emails = max_stores_with_emails or int(os.environ.get("MAX_EMAILS_PER_DAY", "100"))
    if len(stores_with_emails) > max_emails:
        stores_with_emails = stores_with_emails[:max_emails]
        print(f"  Capped at {max_emails} stores (Resend free tier: 100/day)")

    # Step 3 & 4: Audit each store and email
    print("\n[3/4] Running LLM audits and sending emails...")
    sent_count = 0
    llm_reports_count = 0
    for i, store in enumerate(stores_with_emails, 1):
        url = store["Store URL"]
        emails = [e.strip() for e in store["Email(s)"].split(",") if e.strip()]
        if not emails:
            continue

        # Use first email
        to_email = emails[0]

        # Skip if already sent recently (within 7 days)
        if skip_sent and url in sent_log:
            last_sent = sent_log.get(url, "")
            if last_sent:
                try:
                    last_dt = datetime.fromisoformat(last_sent)
                    if (datetime.now() - last_dt).days < 7:
                        print(f"  [{i}] Skip (already sent): {url}")
                        continue
                except (ValueError, TypeError):
                    pass

        print(f"  [{i}/{len(stores_with_emails)}] {url}")

        # Run audit
        audit_data = run_audit(url)
        time.sleep(1)  # Be nice to API

        # Generate HTML – only send if report was generated successfully
        html = audit_to_html(url, audit_data, to_email)
        if html is None:
            print(f"    Skip – audit failed, no email sent")
            continue

        llm_reports_count += 1
        score = get_audit_score(audit_data) or 0
        subject = f"Your store's AI Visibility score is {score}"

        if dry_run:
            print(f"    Would email to {to_email}")
            sent_count += 1
            continue

        # Send email (only when report generated successfully)
        if send_email(to_email, subject, html):
            sent_log[url] = datetime.now().isoformat()
            save_sent_log(sent_log)
            sent_count += 1
            print(f"    Sent to {to_email}")

    stats["llm_reports_generated"] = llm_reports_count
    stats["emails_sent"] = sent_count

    print("\n[4/4] Done.")
    print(f"  Emails sent: {sent_count}")

    # Send daily summary to configured email
    if summary_email:
        print(f"\nSending daily summary to {summary_email}...")
        if send_daily_summary(summary_email, stats):
            print("  Summary sent.")
        else:
            print("  Summary failed to send.")
    else:
        print("\nNo SUMMARY_EMAIL set – skipping daily summary.")

    print("=" * 60)


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Daily LLM audit pipeline")
    parser.add_argument(
        "--regions",
        nargs="+",
        default=["us", "uk"],
        help="Regions to search (us uk germany france)",
    )
    parser.add_argument(
        "--no-skip-sent",
        action="store_true",
        help="Re-email stores even if we sent recently",
    )
    parser.add_argument(
        "--max",
        type=int,
        default=None,
        help="Max stores with emails to process (default: 100 for Resend free tier)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Don't send emails, just show what would happen",
    )
    parser.add_argument(
        "--urls-file",
        default=None,
        help="Use URLs from file instead of DuckDuckGo (for quick testing, e.g. sample_stores.txt)",
    )

    args = parser.parse_args()
    run_full_pipeline(
        regions=args.regions,
        skip_sent=not args.no_skip_sent,
        max_stores_with_emails=args.max,
        dry_run=args.dry_run,
        urls_file=args.urls_file,
    )


if __name__ == "__main__":
    main()
