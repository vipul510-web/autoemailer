# Daily Auto-Send Setup (No Vercel – GitHub Actions)

Your pipeline is **Python** and runs **30+ minutes**. Vercel serverless has a 60s timeout, so it can't run this. **GitHub Actions** is free and supports long-running jobs.

## Resend Free Tier

| Limit | Amount |
|-------|--------|
| **Daily** | 100 emails/day |
| **Monthly** | 3,000 emails/month |

The pipeline is capped at **100 emails/day** by default to stay within the free tier.

---

## Setup Steps

### 1. Create a GitHub repo

If you don't have one yet:

```bash
cd /Users/vipulagarwal/Documents/sellonllm
git init   # if not already
git add .
git commit -m "Add daily LLM audit pipeline"
```

On GitHub: **New repository** → name it `sellonllm` (or any name) → **Create**.

Then:

```bash
git remote add origin https://github.com/YOUR_USERNAME/sellonllm.git
git branch -M main
git push -u origin main
```

### 2. Add secrets

In your repo: **Settings → Secrets and variables → Actions**

| Secret | Value |
|--------|-------|
| `RESEND_API_KEY` | Your Resend API key |
| `SUMMARY_EMAIL` | vipulagarwal.in@gmail.com (for daily summary) |

### 3. Add variables (optional)

| Variable | Value |
|----------|-------|
| `FROM_EMAIL` | `onboarding@resend.dev` (until you verify sellonllm.com in Resend) |

### 4. Done

The workflow runs **daily at 6:00 AM UTC**. To run manually: **Actions → Daily LLM Audit Pipeline → Run workflow**.

---

## Alternative: Render Cron (if you prefer no GitHub)

[Render](https://render.com) has free cron jobs. You'd deploy the `ecommerce-email-scraper` folder as a **Cron Job** and set it to run daily. Requires a Render account.
