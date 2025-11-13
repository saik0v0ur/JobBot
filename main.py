import os
import json
import time
import requests
from bs4 import BeautifulSoup
from collections import defaultdict
from playwright.sync_api import sync_playwright

URL = "https://airtable.com/embed/app17F0kkWQZhC6HB/shrOTtndhc6HSgnYb/tblp8wxvfYam5sD04?viewControls=on"

STATE_FILE = os.path.join(os.path.dirname(__file__), "seen.json")
COMPANY_FILE = os.path.join(os.path.dirname(__file__), "companies.txt")
LOG_FILE = os.path.join(os.path.dirname(__file__), "checked_jobs.log")

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

RESET_INTERVAL = 48 * 3600  # 48 hours in seconds

# ----------------------------------------------------------
# Load / Save Utilities
# ----------------------------------------------------------
def load_seen():
    if os.path.exists(STATE_FILE):
        last_modified = os.path.getmtime(STATE_FILE)
        if (time.time() - last_modified) > RESET_INTERVAL:
            open(STATE_FILE, "w").write("[]")
            print("🕓 Cleared seen.json (older than 48 hours).")
            return set()
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            try:
                return set(json.load(f))
            except Exception:
                return set()
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(list(seen), f)
    print(f"💾 Saved {len(seen)} jobs to {STATE_FILE}")

def load_companies():
    companies = {}
    if os.path.exists(COMPANY_FILE):
        with open(COMPANY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    name, tier = line.strip().split("|", 1)
                    companies[name.lower()] = tier
    print(f"🏢 Loaded {len(companies)} companies from {COMPANY_FILE}")
    return companies

# ----------------------------------------------------------
# Telegram Notification
# ----------------------------------------------------------
def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    try:
        r = requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True},
            timeout=20,
        )
        if r.status_code == 200:
            print("✅ Telegram message sent successfully.")
        else:
            print(f"❌ Telegram API error: {r.status_code} - {r.text}")
    except Exception as e:
        print("❌ Telegram send failed:", e)

# ----------------------------------------------------------
# Logging (auto-clears every 48 hours)
# ----------------------------------------------------------
def write_log(job_text):
    if os.path.exists(LOG_FILE):
        last_modified = os.path.getmtime(LOG_FILE)
        if (time.time() - last_modified) > RESET_INTERVAL:
            open(LOG_FILE, "w").close()
            print("🕓 Cleared checked_jobs.log (older than 48 hours).")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"{job_text}\n")

# ----------------------------------------------------------
# Scraper
# ----------------------------------------------------------
def fetch_jobs():
    with sync_playwright() as p:
        browser = p.firefox.launch(headless=True)
        page = browser.new_page()
        print("🌐 Loading Airtable embed...")
        page.goto(URL, wait_until="networkidle", timeout=90000)
        time.sleep(6)
        html = page.content()
        browser.close()

    soup = BeautifulSoup(html, "html.parser")
    cells = soup.select("div.cell.read")
    rows = defaultdict(dict)

    for cell in cells:
        row_idx = cell.get("data-rowindex")
        col_idx = cell.get("data-columnindex")
        if not row_idx:
            continue

        text = cell.get_text(strip=True)
        link_tag = cell.find("a", href=True)
        if link_tag:
            rows[row_idx]["Link"] = link_tag["href"]

        rows[row_idx][col_idx] = text

    jobs = []
    for idx, row in rows.items():
        position = row.get("0", "Unknown")
        company = row.get("5", "Unknown")
        link = row.get("Link", "No link available")

        jobs.append({
            "Position": position,
            "Company": company,
            "Link": link
        })

    print(f"✅ Extracted {len(jobs)} job rows from rendered DOM.")
    return jobs

# ----------------------------------------------------------
# Main Execution
# ----------------------------------------------------------
def main():
    seen = load_seen()
    companies = load_companies()
    all_jobs = fetch_jobs()
    new_jobs = []

    print(f"✅ Loaded {len(seen)} seen jobs.")
    print(f"🧾 Checking {len(all_jobs)} total listings...")

    for job in all_jobs:
        job_id = job["Link"].strip()  # use the link as a unique identifier
        if job_id in seen:
            continue
        seen.add(job_id)

        matched_company = None
        for name in companies.keys():
            if name in job["Company"].lower():
                matched_company = name
                break

        if not matched_company:
            continue

        tier = companies.get(matched_company, "Unlisted")
        msg = f"[{tier}] {job['Position']} at {job['Company']}\n{job['Link']}"
        write_log(f"NEW: {msg}")
        print("🆕", msg)
        send_telegram(msg)
        new_jobs.append(job)

    save_seen(seen)
    print(f"Checked {len(all_jobs)} listings, found {len(new_jobs)} new.")
    print(f"🗂️ Log saved to {LOG_FILE} (auto-clears every 48h).")

if __name__ == "__main__":
    main()
