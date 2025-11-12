import requests
from bs4 import BeautifulSoup
import json
import os
import re

URL = "https://www.intern-list.com/?k=swe"
STATE_FILE = "seen.json"
COMPANY_FILE = "companies.txt"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ----------------------------
# Helpers
# ----------------------------
def load_seen():
    """Load previously seen job IDs from file."""
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    """Save job IDs to file."""
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)

def load_companies():
    """Load company filters and tiers from companies.txt."""
    companies = {}
    if os.path.exists(COMPANY_FILE):
        with open(COMPANY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    name, tier = line.strip().split("|", 1)
                    companies[name.lower()] = tier
    return companies

def send_telegram(msg):
    """Send a message to Telegram chat."""
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True},
            timeout=20,
        )
    except Exception as e:
        print("❌ Telegram send failed:", e)

# ----------------------------
# Scraper
# ----------------------------
def fetch_jobs():
    """Fetch internships from Intern-List."""
    html = requests.get(URL, timeout=30).text
    soup = BeautifulSoup(html, "html.parser")

    rows = []
    for tr in soup.select("table tr")[1:]:  # skip header
        tds = tr.select("td")
        if len(tds) < 5:
            continue
        job = {
            "Position": tds[0].get_text(strip=True),
            "Season": tds[1].get_text(strip=True),
            "Work Model": tds[2].get_text(strip=True),
            "Location": tds[3].get_text(strip=True),
            "Company": tds[4].get_text(strip=True),
            "Apply Link": tr.select_one("a[href]")["href"] if tr.select_one("a[href]") else None
        }
        rows.append(job)
    return rows

# ----------------------------
# Filters
# ----------------------------
def matches_swe(title):
    """Return True if title contains 'software', 'engineer', and 'intern'."""
    title = re.sub(r"[^a-z\s]", " ", title.lower())
    return all(k in title for k in ["software", "engineer", "intern"])

# ----------------------------
# Main logic
# ----------------------------
def main():
    seen = load_seen()
    companies = load_companies()
    all_jobs = fetch_jobs()
    new_jobs = []

    print(f"✅ Loaded {len(seen)} seen jobs, {len(companies)} companies from filter file.")

    for job in all_jobs:
        job_id = f"{job['Company']}_{job['Position']}"
        if job_id in seen:
            continue
        if not matches_swe(job["Position"]):
            continue
        if companies and job["Company"].lower() not in companies:
            continue

        seen.add(job_id)
        tier = companies.get(job["Company"].lower(), "Unlisted")
        msg = (
            f"[{tier}] {job['Position']} at {job['Company']}\n"
            f"{job['Location']} ({job['Work Model']})\n"
            f"{job.get('Apply Link','')}"
        )
        send_telegram(msg)
        print("📩 Sent:", msg)
        new_jobs.append(job)

    save_seen(seen)
    print(f"Checked {len(all_jobs)} listings, found {len(new_jobs)} new SWE jobs.")

if __name__ == "__main__":
    main()