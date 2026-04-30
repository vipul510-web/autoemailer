#!/usr/bin/env python3
"""
Daily automated pipeline:
1. DuckDuckGo: Discover e-commerce store URLs
2. Scrape emails from stores
3. For each store with email: Run LLM audit, generate report, email it

Run daily via cron or GitHub Actions.
"""

from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

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


def normalize_email(addr: str) -> str:
    return (addr or "").strip().lower()


def normalize_store_url(url: str) -> str:
    """Canonical key for dedupe (https, lowercase host, strip www, trim trailing slash on path)."""
    u = (url or "").strip()
    if not u:
        return ""
    if not u.lower().startswith(("http://", "https://")):
        u = "https://" + u
    parsed = urlparse(u)
    host = (parsed.netloc or "").lower()
    if host.startswith("www."):
        host = host[4:]
    path = parsed.path or ""
    path = path.rstrip("/") or ""
    return f"https://{host}{path}"


def store_host_display(url: str) -> str:
    """Short host for subject lines (e.g. petsupplies.com)."""
    key = normalize_store_url(url)
    if not key:
        return "your store"
    try:
        host = urlparse(key).netloc.lower()
        return host or "your store"
    except Exception:
        return "your store"


def load_sent_log():
    """
    Load recipient + URL send history for deduplication.
    Migrates legacy flat {url: iso} files to {by_url, by_email}.
    """
    if not SENT_LOG.exists():
        return {"by_url": {}, "by_email": {}, "_v": 2}
    with open(SENT_LOG) as f:
        data = json.load(f)
    if isinstance(data, dict) and "by_email" in data and "by_url" in data:
        data.setdefault("_v", 2)
        return data
    # Legacy: entire object was url -> iso date (keys may not be normalized)
    if isinstance(data, dict):
        by_url = {}
        for k, v in data.items():
            if k in ("_v", "by_url", "by_email") or not isinstance(k, str):
                continue
            nk = normalize_store_url(k) or k.strip()
            existing = by_url.get(nk)
            if existing and v:
                ed, vd = _parse_iso(str(existing)), _parse_iso(str(v))
                if ed and vd:
                    by_url[nk] = v if vd > ed else existing
                else:
                    by_url[nk] = v
            else:
                by_url[nk] = v or existing
        return {"by_url": by_url, "by_email": {}, "_v": 2}
    return {"by_url": {}, "by_email": {}, "_v": 2}


def save_sent_log(data):
    """Save sent log."""
    DATA_DIR.mkdir(exist_ok=True)
    with open(SENT_LOG, "w") as f:
        json.dump(data, f, indent=2)


def _parse_iso(dt_str: str):
    if not dt_str:
        return None
    try:
        dt = datetime.fromisoformat(dt_str.replace("Z", "+00:00"))
        if dt.tzinfo is not None:
            dt = dt.replace(tzinfo=None)
        return dt
    except (ValueError, TypeError):
        return None


def recently_sent(sent_log, email: str, store_url: str, cooldown_days: int):
    """
    True if this email address or canonical URL was mailed within cooldown_days.
    Returns (skip: bool, reason: str).
    """
    if cooldown_days <= 0:
        return False, ""
    now = datetime.now()
    email_key = normalize_email(email)
    url_key = normalize_store_url(store_url) or store_url.strip()

    for label, bucket, key in (
        ("email", sent_log.get("by_email", {}), email_key),
        ("url", sent_log.get("by_url", {}), url_key),
    ):
        if not key:
            continue
        last = _parse_iso(bucket.get(key, ""))
        if last and (now - last).days < cooldown_days:
            return True, f"same {label} within {cooldown_days}d"
    return False, ""


def record_sent(sent_log, email: str, store_url: str):
    """Record successful send under both email and normalized URL."""
    iso = datetime.now().isoformat()
    ek = normalize_email(email)
    uk = normalize_store_url(store_url) or store_url.strip()
    if ek:
        sent_log.setdefault("by_email", {})[ek] = iso
    if uk:
        sent_log.setdefault("by_url", {})[uk] = iso
    sent_log["_v"] = 2


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
        You received this one-time audit because your store appeared in public e-commerce search results we sampled.
        If this isn’t useful, reply with &quot;unsubscribe&quot; and we won’t email again.
    </p>
    <p style="font-size:0.85em;color:#6b7280;">SellOnLLM · <a href="https://sellonllm.com">sellonllm.com</a></p>
</body>
</html>
"""


def audit_to_plaintext(store_url, audit_data):
    """Plain-text counterpart to the HTML body (helps inbox placement)."""
    if "error" in audit_data:
        return None
    summary = audit_data.get("summary", {})
    checks = summary.get("checks", {})
    total = len(checks)
    passed = sum(1 for c in checks.values() if c.get("percentage", 0) >= 50)
    overall = round((passed / total) * 100) if total else 0
    host = store_host_display(store_url)
    lines = [
        f"LLM / SEO readiness snapshot for {host}",
        f"Analyzed URL: {store_url}",
        f"Overall score: {overall}/100",
        "",
        "Checks:",
    ]
    for key, data in checks.items():
        label = CHECK_LABELS.get(key, key.replace("_", " ").title())
        pct = data.get("percentage", 0)
        mark = "OK" if pct >= 50 else "Needs work"
        detail = (data.get("details") or "—").strip()
        if len(detail) > 160:
            detail = detail[:157] + "..."
        lines.append(f"- {label}: {pct}% ({mark}) — {detail}")
    lines.extend(
        [
            "",
            "More visibility on AI platforms:",
            "https://apps.shopify.com/llm-analytics",
            "",
            "— SellOnLLM · https://sellonllm.com",
        ]
    )
    return "\n".join(lines)


def send_email(to_email, subject, html_body, text_body=None):
    """Send email via Resend API."""
    api_key = (os.environ.get("RESEND_API_KEY") or "").strip()
    from_email = (os.environ.get("FROM_EMAIL") or "").strip() or "onboarding@resend.dev"
    sender_name = os.environ.get("SENDER_NAME", "Vipul from SellOnLLM").strip()

    # Format: "Name <email>" or just "email" if no name
    from_field = f"{sender_name} <{from_email}>" if sender_name else from_email
    unsub = (os.environ.get("LIST_UNSUBSCRIBE_MAILTO") or "").strip()
    if not unsub and from_email and "@" in from_email:
        unsub = f"mailto:{from_email}?subject=unsubscribe"

    payload = {
        "from": from_field,
        "to": [to_email],
        "subject": subject,
        "html": html_body,
    }
    if text_body:
        payload["text"] = text_body
    if unsub:
        payload["headers"] = {
            "List-Unsubscribe": f"<{unsub}>",
        }

    if not api_key:
        print("  [SKIP] RESEND_API_KEY not set - add it as a GitHub secret")
        return False

    try:
        resp = requests.post(
            "https://api.resend.com/emails",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "User-Agent": "SellOnLLM-AuditPipeline/1.1",
            },
            json=payload,
            timeout=10,
        )
        resp.raise_for_status()
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 403:
            try:
                err_body = e.response.json()
                msg = err_body.get("message", str(e))
            except Exception:
                msg = str(e)
            print(f"  [ERROR] 403 Forbidden: {msg}")
            print("  → Verify your domain at resend.com/domains and use FROM_EMAIL from that domain")
            print("  → onboarding@resend.dev can only send to your Resend account email")
        else:
            print(f"  [ERROR] Email failed: {e}")
        return False
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


def load_stores_from_excel(excel_path):
    """Load stores with emails from an Excel file (Store URL, Email(s), Email Count columns)."""
    import pandas as pd
    df = pd.read_excel(excel_path)
    # Normalize column names (handle slight variations)
    col_map = {c: c for c in df.columns}
    url_col = next((c for c in df.columns if "url" in str(c).lower() or "store" in str(c).lower()), "Store URL")
    email_col = next((c for c in df.columns if "email" in str(c).lower()), "Email(s)")
    count_col = next((c for c in df.columns if "count" in str(c).lower()), "Email Count")
    result = []
    for _, row in df.iterrows():
        count = row.get(count_col, 0)
        if pd.notna(count) and int(count) > 0:
            result.append({
                "Store URL": str(row.get(url_col, "")).strip(),
                "Email(s)": str(row.get(email_col, "")).strip(),
                "Email Count": int(count),
            })
    return [r for r in result if r["Store URL"] and r["Email(s)"]]


def run_full_pipeline(
    regions=None,
    skip_sent=True,
    max_stores_with_emails=None,
    dry_run=False,
    urls_file=None,
    from_excel=None,
):
    """
    Run the full daily pipeline.
    skip_sent: Skip recipients we already emailed within SENT_COOLDOWN_DAYS (default 90), by email + URL.
    max_stores_with_emails: Limit how many stores to process (for testing)
    dry_run: Don't send emails, just log what would happen
    urls_file: Skip DuckDuckGo and use URLs from this file (for quick testing)
    from_excel: Skip discovery AND scraping; use Store URL + Email(s) from this Excel file
    """
    DATA_DIR.mkdir(exist_ok=True)
    sent_log = load_sent_log()
    summary_email = os.environ.get("SUMMARY_EMAIL", "").strip()
    try:
        cooldown_days = int(os.environ.get("SENT_COOLDOWN_DAYS", "90"))
    except ValueError:
        cooldown_days = 90

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
    # Log config status (without exposing secrets)
    has_key = bool((os.environ.get("RESEND_API_KEY") or "").strip())
    from_em = (os.environ.get("FROM_EMAIL") or "").strip() or "onboarding@resend.dev"
    print(f"RESEND_API_KEY: {'configured' if has_key else 'NOT SET (emails will be skipped)'}")
    print(f"FROM_EMAIL: {from_em}")
    if from_em == "onboarding@resend.dev":
        print("  ⚠ onboarding@resend.dev → 403 when sending to brands. Verify domain at resend.com/domains")
    print(f"SENT_COOLDOWN_DAYS: {cooldown_days} (skip if same email or same store URL was mailed more recently)")

    # Step 1 & 2: Discover + scrape, OR load from Excel (skip both)
    if from_excel and Path(from_excel).exists():
        print(f"\n[1/2] Using stores + emails from {from_excel} (skip discovery & scraping)...")
        stores_with_emails = load_stores_from_excel(from_excel)
        store_urls = [s["Store URL"] for s in stores_with_emails]
        stats["urls_scraped"] = len(store_urls)
        stats["sample_urls"] = store_urls.copy()
        print(f"  Found {len(stores_with_emails)} stores with emails")
    elif urls_file and Path(urls_file).exists():
        print(f"\n[1/4] Using URLs from {urls_file} (skip DuckDuckGo)...")
        with open(urls_file) as f:
            store_urls = [u.strip() for u in f if u.strip() and not u.startswith("#")]
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

        # Skip if this address or canonical URL was emailed within cooldown (GitHub cache bug fix + email-level dedupe)
        if skip_sent and cooldown_days > 0:
            dup, reason = recently_sent(sent_log, to_email, url, cooldown_days)
            if dup:
                print(f"  [{i}] Skip ({reason}): {to_email} ← {url}")
                continue

        print(f"  [{i}/{len(stores_with_emails)}] {url}")

        # Run audit
        audit_data = run_audit(url)
        time.sleep(1)  # Be nice to API

        # Generate HTML – only send if report was generated successfully
        html = audit_to_html(url, audit_data, to_email)
        if html is None:
            print(f"    Skip – audit failed, no email sent")
            continue

        plain = audit_to_plaintext(url, audit_data)

        llm_reports_count += 1
        score = get_audit_score(audit_data) or 0
        host = store_host_display(url)
        subject = f"{host}: LLM/SEO snapshot ({score}/100) — one-time audit"

        if dry_run:
            print(f"    Would email to {to_email}")
            sent_count += 1
            continue

        # Send email (only when report generated successfully)
        if send_email(to_email, subject, html, plain):
            record_sent(sent_log, to_email, url)
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
        help="Use URLs from file instead of DuckDuckGo (for quick testing)",
    )
    parser.add_argument(
        "--from-excel",
        default=None,
        help="Use Store URL + Email(s) from Excel file (skip discovery & scraping). Use data/store_emails.xlsx from previous run.",
    )

    args = parser.parse_args()
    run_full_pipeline(
        regions=args.regions,
        skip_sent=not args.no_skip_sent,
        max_stores_with_emails=args.max,
        dry_run=args.dry_run,
        urls_file=args.urls_file,
        from_excel=args.from_excel,
    )


if __name__ == "__main__":
    main()
