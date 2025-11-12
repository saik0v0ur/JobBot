from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
import json, os, time, requests
from collections import defaultdict

URL = "https://airtable.com/embed/app17F0kkWQZhC6HB/shrOTtndhc6HSgnYb/tblp8wxvfYam5sD04?viewControls=on"
STATE_FILE = "seen.json"
COMPANY_FILE = "companies.txt"
LOG_FILE = "checked_jobs.log"

TELEGRAM_TOKEN = "8576999816:AAGBc-LZJHBqEElA-gc41v4da5eF_0TA2Ts"
CHAT_ID = "6634736969"

def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def load_companies():
    companies = {}
    if os.path.exists(COMPANY_FILE):
        with open(COMPANY_FILE, "r") as f:
            for line in f:
                if "|" in line:
                    name, tier = line.strip().split("|", 1)
                    companies[name.lower()] = tier
    return companies

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("⚠️ Telegram not configured.")
        return
    r = requests.post(
        f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
        data={"chat_id": CHAT_ID, "text": msg, "disable_web_page_preview": True},
        timeout=20,
    )
    if r.status_code == 200:
        print("✅ Telegram message sent successfully.")
    else:
        print(f"❌ Telegram error: {r.status_code}")

def write_log(entry):
    with open(LOG_FILE, "a") as f:
        f.write(entry + "\n")

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

        # Extract main text
        text = cell.get_text(strip=True)

        # Extract hyperlink if present
        link_tag = cell.find("a", href=True)
        if link_tag:
            href = link_tag["href"]
            rows[row_idx]["Link"] = href

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


def main():
    seen = load_seen()
    companies = load_companies()
    all_jobs = fetch_jobs()
    new_jobs = []

    for job in all_jobs:
        job_id = f"{job['Position']}@{job['Company']}"
        if job_id in seen:
            continue
        seen.add(job_id)

        # Match the company against your filter list (case-insensitive substring match)
        matched_company = None
        for name in companies.keys():
            if name in job["Company"].lower():
                matched_company = name
                break

        if not matched_company:
            continue

        tier = companies.get(matched_company, "Unlisted")
        msg = f"[{tier}] {job['Position']} at {job['Company']}\n{job['Link']}"
        write_log("NEW: " + msg)
        print("🆕", msg)
        send_telegram(msg)
        new_jobs.append(job)

    save_seen(seen)
    print(f"Checked {len(all_jobs)} listings, found {len(new_jobs)} new.")

if __name__ == "__main__":
    main()
