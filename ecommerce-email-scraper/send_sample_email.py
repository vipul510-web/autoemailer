#!/usr/bin/env python3
"""
Send a sample audit email for testing.
Usage: RESEND_API_KEY=re_xxxxx python send_sample_email.py
"""

import os
import sys

# Add parent for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from daily_pipeline import run_audit, audit_to_html, send_email

URL = "https://woodchop.in"
TO_EMAIL = "vipulagarwal.in@gmail.com"

if __name__ == "__main__":
    if not os.environ.get("RESEND_API_KEY"):
        print("Set RESEND_API_KEY first: export RESEND_API_KEY=re_xxxxx")
        sys.exit(1)

    print(f"Running audit for {URL}...")
    audit_data = run_audit(URL)

    if "error" in audit_data:
        print("Audit failed:", audit_data["error"])
        sys.exit(1)

    html = audit_to_html(URL, audit_data, TO_EMAIL)
    if not html:
        print("Could not generate email")
        sys.exit(1)

    from daily_pipeline import get_audit_score
    score = get_audit_score(audit_data) or 0
    subject = f"Your store's AI Visibility score is {score}"
    if send_email(TO_EMAIL, subject, html):
        print(f"✓ Email sent to {TO_EMAIL}")
    else:
        print("Email failed")
        sys.exit(1)
