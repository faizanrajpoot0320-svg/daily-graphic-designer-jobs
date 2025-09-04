# Remote Entry-Level Social Media Graphic Designer — Daily Email Automation

This repo contains a **Python + GitHub Actions** automation that **every day at 12:00 PM (Asia/Karachi)** searches multiple job boards for **remote, entry-level Graphic Designer (social media)** roles and emails you fresh listings.

## Sources Covered
- **RemoteOK** (Design category + keyword search)
- **We Work Remotely** (Design category)
- **Wellfound (AngelList)** — public listings page (best-effort parsing)
- **Workable Discover** — public search (best-effort parsing)
- **Ashby** job boards — aggregated search endpoint (best-effort)
- **Lever & Greenhouse** — best-effort via public search pages (not all companies expose global feeds)

> Note: Scraping **LinkedIn / Indeed** is intentionally **disabled by default** due to ToS. If you have API access or explicit permission, you can add a module and enable it.

## What it does
- Runs daily at **12:00 PM Asia/Karachi (UTC+5)** via GitHub Actions
- Fetches new job posts from the last **DAYS_BACK** days
- Filters by:
  - keywords: `graphic designer`, `social media`
  - level: `entry level`, `junior`, `associate`
  - remote: `remote`, `work from home`, `anywhere`, `global`
- Extracts **title, company, link, date, salary (if available)**
- Sends a nicely formatted **email** to `EMAIL_TO`

## Quick Start

1. **Create a repository** on GitHub and upload all files from this folder.
2. Copy `.env.example` to `.env` and update values. **For Gmail**, create an **App Password** (Account → Security → App passwords) and use it as `SMTP_PASS`.
3. In your repository, go to **Settings → Secrets and variables → Actions → New repository secret** and add:
   - `ENV_FILE` with the **entire contents of your `.env`** file.
4. Commit & push. The workflow will run automatically at **12:00 PM Asia/Karachi** every day.
5. To test immediately: go to **Actions → “Daily Job Finder” → Run workflow → “Run workflow”**.

## Customization
- Edit `.env` to tweak keywords, DAYS_BACK, min salary, and recipient.
- Add/remove sources in `main.py` as you like.

## Disclaimer
Sites change HTML frequently; the script is **best-effort** and skips sources that fail gracefully. Avoid scraping sites that prohibit it.
