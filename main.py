import os
import json
import time
import re
import requests

from bs4 import BeautifulSoup
from datetime import datetime, timedelta
from urllib.parse import urlparse

# ============================================================
# Configuration
# ============================================================

AIRTABLE_URL = "https://airtable.com/embed/app17F0kkWQZhC6HB/shrOTtndhc6HSgnYb/tblp8wxvfYam5sD04?viewControls=on"
COMPANY_FILE = "companies.txt"
SEEN_FILE = "seen.json"
LOG_FILE = "checked_jobs.log"
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ============================================================
# Helper functions
# ============================================================

def normalize_link(link):
    """Strip query parameters for consistent job IDs."""
    try:
        parsed = urlparse(link)
        return f"{parsed.scheme}://{parsed.netloc}{parsed.path}"
    except:
        return link

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram not configured — skipping message.")
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": TELEGRAM_CHAT_ID, "text": message}
    try:
        requests.post(url, data=data, timeout=10)
        print("✅ Telegram message sent successfully.")
    except Exception as e:
        print("❌ Telegram send failed:", e)

def load_seen_jobs():
    """Load previous seen jobs (supporting both list and dict formats)."""
    if not os.path.exists(SEEN_FILE):
        return {}
    with open(SEEN_FILE, "r") as f:
        data = json.load(f)
        if isinstance(data, list):  # backward compatibility
            return {job: {"timestamp": "unknown"} for job in data}
        return data

def save_seen_jobs(seen):
    """Save jobs with timestamps."""
    with open(SEEN_FILE, "w") as f:
        json.dump(seen, f, indent=2)

def write_log(entry):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a") as f:
        f.write(f"[{timestamp}] {entry}\n")

def clear_old_logs():
    if not os.path.exists(LOG_FILE):
        return
    last_modified = datetime.fromtimestamp(os.path.getmtime(LOG_FILE))
    if datetime.now() - last_modified > timedelta(hours=48):
        open(LOG_FILE, "w").close()
        print("🧹 Cleared old logs (older than 48 hours).")

def load_companies():
    companies = {}
    with open(COMPANY_FILE, "r") as f:
        for line in f:
            if "|" in line:
                name, tier = line.strip().split("|", 1)
                companies[name.lower()] = tier
    print(f"📊 Loaded {len(companies)} companies from {COMPANY_FILE}")
    return companies

# ============================================================
# Core Scraper
# ============================================================

def scrape_airtable():
    print("🌐 Loading Airtable embed...")
    html = requests.get(AIRTABLE_URL).text
    soup = BeautifulSoup(html, "html.parser")

    rows = soup.find_all("div", {"data-testid": re.compile(r"gridCell-\d+:")})
    print(f"✅ Extracted {len(rows)//6} job rows from rendered DOM.")  # approximate row count

    jobs = []
    for i in range(0, len(rows), 6):
        try:
            pos = rows[i].text.strip()
            date = rows[i+1].text.strip()
            link_tag = rows[i+2].find("a")
            link = link_tag["href"] if link_tag else "Unknown"
            model = rows[i+3].text.strip()
            location = rows[i+4].text.strip()
            company = rows[i+5].text.strip()
            jobs.append({
                "Position": pos,
                "Date": date,
                "Link": link,
                "Model": model,
                "Location": location,
                "Company": company
            })
        except:
            continue
    return jobs

# ============================================================
# Main Execution
# ============================================================

def main():
    clear_old_logs()
    companies = load_companies()
    seen = load_seen_jobs()

    jobs = scrape_airtable()
    print(f"✅ Loaded {len(seen)} seen jobs.")
    print(f"📄 Checking {len(jobs)} total listings...")

    new_jobs = []
    for job in jobs:
        job_id = f"{job['Position']}@{job['Company']}@{normalize_link(job['Link'])}"
        if job_id in seen:
            continue

        # Add timestamp
        seen[job_id] = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "position": job["Position"],
            "company": job["Company"],
            "link": normalize_link(job["Link"])
        }

        matched_company = None
        for name in companies.keys():
            pattern = r"\b" + re.escape(name.lower()) + r"\b"
            if re.search(pattern, job["Company"].lower()):
                matched_company = name
                print(f"🔍 Matched company: {job['Company']} → from companies.txt entry: {name}")
                break

        if not matched_company:
            continue

        tier = companies.get(matched_company, "Unlisted")
        msg = f"[{tier}] {job['Position']} at {job['Company']}\n{job['Link']}"
        write_log(f"NEW: {msg}")
        print("🆕", msg)
        send_telegram(msg)
        new_jobs.append(job)

    save_seen_jobs(seen)
    print(f"💾 Saved {len(seen)} jobs to {SEEN_FILE}")
    print(f"Checked {len(jobs)} listings, found {len(new_jobs)} new.")
    print(f"📁 Log saved to {LOG_FILE} (auto-clears every 48h).")

# ============================================================
# Run Script
# ============================================================

if __name__ == "__main__":
    main()
