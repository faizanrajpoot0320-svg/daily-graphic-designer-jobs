#!/usr/bin/env python3
import os
import re
import time
import json
import smtplib
import pytz
import feedparser
import requests
from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dateutil import parser as dateparser

TIMEZONE = os.getenv("TIMEZONE", "Asia/Karachi")
tz = pytz.timezone(TIMEZONE)

KEYWORDS = [k.strip().lower() for k in os.getenv("KEYWORDS", "graphic designer,social media").split(",") if k.strip()]
LEVEL_KEYWORDS = [k.strip().lower() for k in os.getenv("LEVEL_KEYWORDS", "entry level,junior,associate").split(",") if k.strip()]
REMOTE_KEYWORDS = [k.strip().lower() for k in os.getenv("REMOTE_KEYWORDS", "remote,work from home,anywhere,global").split(",") if k.strip()]
DAYS_BACK = int(os.getenv("DAYS_BACK", "2"))
MIN_SALARY_USD = int(os.getenv("MIN_SALARY_USD", "0"))

SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER")
SMTP_PASS = os.getenv("SMTP_PASS")
EMAIL_TO  = os.getenv("EMAIL_TO")

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; JobBot/1.0; +https://example.com/bot)"
}

def within_days(dt: datetime, days: int) -> bool:
    try:
        now = datetime.now(tz)
        return (now - dt).days <= days
    except Exception:
        return True

def parse_salary(text: str):
    """
    Very rough salary extraction. Returns (amount, currency) if USD-ish.
    """
    if not text:
        return None
    m = re.search(r'(\$|USD)\s?([0-9]{2,3}(?:[,0-9]{0,3})?)([kK])?', text)
    if m:
        amt = m.group(2).replace(",", "")
        if m.group(3):
            amt = str(int(amt) * 1000)
        try:
            return int(amt), "USD"
        except:
            return None
    return None

def matches_filters(title, company, location, desc):
    blob = " ".join([title or "", company or "", location or "", desc or ""]).lower()

    kw_ok = all(any(k in blob for k in [key]) for key in KEYWORDS) if KEYWORDS else True
    # Above ensures presence of each provided keyword individually; loosen if needed.
    # Alternatively, require at least one of keywords:
    # kw_ok = any(k in blob for k in KEYWORDS)

    lvl_ok = any(k in blob for k in LEVEL_KEYWORDS) if LEVEL_KEYWORDS else True
    rem_ok = any(k in blob for k in REMOTE_KEYWORDS) if REMOTE_KEYWORDS else True
    return kw_ok and lvl_ok and rem_ok

def normalize_item(source, title, company, link, date_str=None, location=None, desc=None, salary_text=None):
    # Parse date
    dt = None
    if date_str:
        try:
            dt = dateparser.parse(date_str)
            if not dt.tzinfo:
                dt = tz.localize(dt)
            else:
                dt = dt.astimezone(tz)
        except Exception:
            dt = None
    if not dt:
        dt = datetime.now(tz)

    # Parse salary
    salary = parse_salary(salary_text or desc or title)

    return {
        "source": source,
        "title": (title or "").strip(),
        "company": (company or "").strip(),
        "link": (link or "").strip(),
        "date": dt.isoformat(),
        "location": (location or "").strip() if location else "",
        "salary": salary[0] if salary else None,
        "salary_currency": salary[1] if salary else None,
        "desc": (desc or "").strip(),
    }

def fetch_remoteok():
    # RSS for design jobs
    url = "https://remoteok.com/remote-design-jobs.rss"
    out = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = e.get("title", "")
            link = e.get("link", "")
            summary = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ")
            date_str = e.get("published") or e.get("updated")
            company = e.get("author") or ""
            item = normalize_item("RemoteOK", title, company, link, date_str, "", summary, summary)
            if matches_filters(item["title"], item["company"], item["location"], item["desc"]):
                out.append(item)
    except Exception as ex:
        print("RemoteOK error:", ex)
    return out

def fetch_wwr():
    # We Work Remotely: design category
    url = "https://weworkremotely.com/categories/remote-design-jobs.rss"
    out = []
    try:
        feed = feedparser.parse(url)
        for e in feed.entries:
            title = e.get("title", "")
            link = e.get("link", "")
            summary = BeautifulSoup(e.get("summary", ""), "html.parser").get_text(" ")
            date_str = e.get("published") or e.get("updated")
            # Company often embedded in title like "Company — Role"
            company = ""
            if "—" in title:
                parts = [p.strip() for p in title.split("—", 1)]
                if len(parts) == 2:
                    company, title = parts[0], parts[1]
            item = normalize_item("WeWorkRemotely", title, company, link, date_str, "Remote", summary, summary)
            if matches_filters(item["title"], item["company"], item["location"], item["desc"]):
                out.append(item)
    except Exception as ex:
        print("WWR error:", ex)
    return out

def fetch_wellfound():
    # Best-effort HTML parse of Wellfound search results for "graphic designer"
    url = "https://wellfound.com/role/graphic-designer"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        # Wellfound uses client-side rendering; fallback to minimal parse of <a> tags that contain job links
        for a in soup.find_all("a", href=True):
            href = a["href"]
            if "/jobs/" in href and "graphic" in a.get_text(" ").lower():
                title = a.get_text(" ").strip()
                link = "https://wellfound.com" + href if href.startswith("/") else href
                item = normalize_item("Wellfound", title, "", link, None, "Remote", title, title)
                if matches_filters(item["title"], item["company"], item["location"], item["desc"]):
                    out.append(item)
    except Exception as ex:
        print("Wellfound error:", ex)
    return out

def fetch_workable():
    # Workable Discover search (public): keyword-based HTML parse
    url = "https://www.workable.com/jobs?remote=true&query=graphic%20designer"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        for card in soup.select("a.CardItemstyles__Link-sc"):
            link = card.get("href")
            title = card.get_text(" ").strip()
            company = ""
            if link:
                link = "https://www.workable.com" + link if link.startswith("/") else link
            item = normalize_item("Workable", title, company, link, None, "Remote", title, title)
            if matches_filters(item["title"], item["company"], item["location"], item["desc"]):
                out.append(item)
    except Exception as ex:
        print("Workable error:", ex)
    return out

def fetch_ashby():
    # Ashby job boards - aggregated search endpoint (best-effort)
    # Many startups use Ashby; we try a keyword search page and parse links
    url = "https://jobs.ashbyhq.com/jobs?query=graphic%20designer&remote=true"
    out = []
    try:
        html = requests.get(url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ").strip()
            if "/jobs/" in href and ("graphic" in text.lower() or "designer" in text.lower()):
                link = href if href.startswith("http") else f"https://jobs.ashbyhq.com{href}"
                title = text
                item = normalize_item("Ashby", title, "", link, None, "Remote", title, title)
                if matches_filters(item["title"], item["company"], item["location"], item["desc"]):
                    out.append(item)
    except Exception as ex:
        print("Ashby error:", ex)
    return out

def fetch_lever_greenhouse():
    # Best-effort search pages for Lever / Greenhouse (not comprehensive)
    results = []
    # Greenhouse search (public search page)
    gh_url = "https://boards.greenhouse.io/embed/job_board?for=&remote=true&query=graphic%20designer"
    try:
        html = requests.get(gh_url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ").strip()
            if "/jobs/" in href and ("graphic" in text.lower() or "designer" in text.lower()):
                link = href if href.startswith("http") else f"https://boards.greenhouse.io{href}"
                results.append(normalize_item("Greenhouse", text, "", link, None, "Remote", text, text))
    except Exception as ex:
        print("Greenhouse error:", ex)

    # Lever: generic search page (limited)
    lever_url = "https://jobs.lever.co/search?department=Design&location=Remote&keywords=graphic%20designer"
    try:
        html = requests.get(lever_url, headers=HEADERS, timeout=20).text
        soup = BeautifulSoup(html, "html.parser")
        for a in soup.find_all("a", href=True):
            href = a["href"]
            text = a.get_text(" ").strip()
            if "/jobs/" in href and ("graphic" in text.lower() or "designer" in text.lower()):
                link = href if href.startswith("http") else f"https://jobs.lever.co{href}"
                results.append(normalize_item("Lever", text, "", link, None, "Remote", text, text))
    except Exception as ex:
        print("Lever error:", ex)

    return results

def fetch_all():
    items = []
    items += fetch_remoteok()
    items += fetch_wwr()
    items += fetch_wellfound()
    items += fetch_workable()
    items += fetch_ashby()
    items += fetch_lever_greenhouse()

    # Filter recent
    cutoff = datetime.now(tz) - timedelta(days=DAYS_BACK)
    filtered = []
    for it in items:
        try:
            dt = dateparser.parse(it["date"])
            if dt.tzinfo:
                dt = dt.astimezone(tz)
            else:
                dt = tz.localize(dt)
        except Exception:
            dt = datetime.now(tz)
        if dt >= cutoff and matches_filters(it["title"], it["company"], it["location"], it["desc"]):
            # Salary filter
            if MIN_SALARY_USD and it["salary"] and it["salary_currency"] == "USD":
                if it["salary"] < MIN_SALARY_USD:
                    continue
            filtered.append(it)

    # De-duplicate by link
    seen = set()
    deduped = []
    for it in filtered:
        if it["link"] and it["link"] not in seen:
            seen.add(it["link"])
            deduped.append(it)

    # Sort by date desc
    deduped.sort(key=lambda x: x["date"], reverse=True)
    return deduped

def send_email(jobs):
    if not SMTP_USER or not SMTP_PASS or not EMAIL_TO:
        print("Email not configured. Skipping send.")
        return

    now = datetime.now(tz).strftime("%Y-%m-%d %H:%M")
    subject = f"[Daily Jobs] Remote Entry-Level Social Media Graphic Designer — {now}"
    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = SMTP_USER
    msg["To"] = EMAIL_TO

    if not jobs:
        html = f"<p>No new matching jobs found in the last {DAYS_BACK} day(s).</p>"
        text = f"No new matching jobs found in the last {DAYS_BACK} day(s)."
    else:
        rows = []
        for j in jobs:
            salary = f"${j['salary']:,} {j['salary_currency']}" if j.get("salary") else "—"
            date_local = dateparser.parse(j["date"]).astimezone(tz).strftime("%Y-%m-%d %H:%M")
            rows.append(f"""
            <tr>
              <td>{j['source']}</td>
              <td><a href="{j['link']}" target="_blank">{j['title']}</a></td>
              <td>{j['company'] or '—'}</td>
              <td>{j['location'] or 'Remote'}</td>
              <td>{salary}</td>
              <td>{date_local}</td>
            </tr>
            """)
        html = f"""
        <p>Here are the latest matches (last {DAYS_BACK} day(s)):</p>
        <table border="1" cellpadding="6" cellspacing="0">
          <thead>
            <tr>
              <th>Source</th><th>Title</th><th>Company</th><th>Location</th><th>Salary</th><th>Date</th>
            </tr>
          </thead>
          <tbody>
            {''.join(rows)}
          </tbody>
        </table>
        """
        # Plain-text fallback
        text_lines = []
        for j in jobs:
            salary = f"${j['salary']:,} {j['salary_currency']}" if j.get("salary") else "—"
            date_local = dateparser.parse(j["date"]).astimezone(tz).strftime("%Y-%m-%d %H:%M")
            text_lines.append(f"- [{j['source']}] {j['title']} @ {j['company'] or '—'} | {salary} | {date_local} | {j['link']}")
        text = "Here are the latest matches:\\n" + "\\n".join(text_lines)

    part1 = MIMEText(text, "plain")
    part2 = MIMEText(html, "html")
    msg.attach(part1)
    msg.attach(part2)

    with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
        server.starttls()
        server.login(SMTP_USER, SMTP_PASS)
        server.sendmail(SMTP_USER, [EMAIL_TO], msg.as_string())

def main():
    jobs = fetch_all()
    print(f"Found {len(jobs)} matching jobs.")
    send_email(jobs)

if __name__ == "__main__":
    main()
