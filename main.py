import os
import json
import time
import re
import requests
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright

# ============================================================
# Configuration
# ============================================================

# The URL of the Airtable Embed
AIRTABLE_URL = "https://airtable.com/embed/app17F0kkWQZhC6HB/shrOTtndhc6HSgnYb/tblp8wxvfYam5sD04?viewControls=on"

# File paths
COMPANY_FILE = "companies.txt"
SEEN_FILE = "seen.json"
LOG_FILE = "checked_jobs.log"

# Telegram settings (Try to load from Env, fallback to hardcoded if testing locally)
TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN", "8576999816:AAGBc-LZJHBqEElA-gc41v4da5eF_0TA2Ts")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "6634736969")

# ============================================================
# Helper Functions
# ============================================================

def load_companies():
    """Loads company tiers from text file."""
    companies = {}
    if os.path.exists(COMPANY_FILE):
        with open(COMPANY_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if "|" in line:
                    name, tier = line.strip().split("|", 1)
                    companies[name.lower()] = tier
    print(f"🏢 Loaded {len(companies)} companies.")
    return companies

def load_seen():
    """Loads history of jobs to avoid duplicates."""
    if not os.path.exists(SEEN_FILE):
        return {}
    try:
        with open(SEEN_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            # Handle format if it's a list (legacy) vs dict
            if isinstance(data, list):
                return {url: {"timestamp": "legacy"} for url in data}
            return data
    except:
        return {}

def save_seen(seen_data):
    with open(SEEN_FILE, "w", encoding="utf-8") as f:
        json.dump(seen_data, f, indent=2)

def send_telegram(message):
    if not TELEGRAM_TOKEN or not TELEGRAM_CHAT_ID:
        print("⚠️ Telegram credentials missing.")
        return
    try:
        url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
        payload = {
            "chat_id": TELEGRAM_CHAT_ID,
            "text": message,
            "disable_web_page_preview": True
        }
        requests.post(url, data=payload, timeout=10)
        print("✅ Notification sent.")
    except Exception as e:
        print(f"❌ Telegram failed: {e}")

def write_log(message):
    """Simple logger."""
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(f"[{ts}] {message}\n")

# ============================================================
# The Core Logic (Network Interceptor)
# ============================================================

def fetch_airtable_data():
    """
    Uses Playwright to intercept the 'readSharedViewData' JSON response.
    """
    jobs_found = []
    
    with sync_playwright() as p:
        print("🌐 Launching browser...")
        # Use chromium (matches GitHub Actions)
        browser = p.chromium.launch(headless=True)
        page = browser.new_page()

        # Container for the intercepted data
        intercepted_data = {"json": None}

        def handle_response(response):
            if "readSharedViewData" in response.url and response.status == 200:
                try:
                    data = response.json()
                    # Only grab if it actually has table data
                    if "data" in data and "table" in data["data"]:
                        print("⚡ Intercepted Airtable data packet!")
                        intercepted_data["json"] = data
                except:
                    pass

        page.on("response", handle_response)

        print(f"⏳ Navigating to Airtable...")
        try:
            # CHANGED: wait_until="domcontentloaded" is much faster than "networkidle"
            # We also added a try/except block to ignore timeouts if we get the data
            page.goto(AIRTABLE_URL, wait_until="domcontentloaded", timeout=20000)
            
            # Wait a fixed time to allow the specific XHR request to fire
            print("⏳ Waiting for data stream...")
            page.wait_for_timeout(5000)
            
        except Exception as e:
            print(f"⚠️ Page loading timed out, checking if we got data anyway...")

        browser.close()

        # --- Process the intercepted JSON ---
        raw_json = intercepted_data["json"]
        if not raw_json:
            print("❌ Failed to intercept data. Airtable might be blocking or slow.")
            return []

        try:
            table_data = raw_json.get("data", {}).get("table", {})
            columns = table_data.get("columns", [])
            rows = table_data.get("rows", [])

            # Map Column IDs to Names
            col_map = {col["id"]: col["name"] for col in columns}
            
            for row in rows:
                cell_values = row.get("cellValues", {})
                clean_job = {}
                for col_id, val in cell_values.items():
                    col_name = col_map.get(col_id, col_id)
                    clean_job[col_name] = val
                
                # Normalize keys
                normalized_job = {
                    "Company": clean_job.get("Company", "Unknown"),
                    "Position": clean_job.get("Position", clean_job.get("Role", "Unknown")),
                    "Link": clean_job.get("Link", clean_job.get("Apply", "Unknown")),
                    "Location": clean_job.get("Location", "Unknown")
                }
                jobs_found.append(normalized_job)
                
        except Exception as e:
            print(f"❌ Error parsing JSON structure: {e}")
            return []

    return jobs_found

# ============================================================
# Main
# ============================================================

def main():
    companies = load_companies()
    seen = load_seen()
    
    print("🚀 Starting scraper...")
    jobs = fetch_airtable_data()
    print(f"📊 Extracted {len(jobs)} total jobs via API interception.")

    new_count = 0
    
    for job in jobs:
        # Sanitize data
        company = job.get("Company", "Unknown")
        position = job.get("Position", "Unknown")
        link = job.get("Link", "")

        if not isinstance(link, str) or not link.startswith("http"):
            # Sometimes link is missing or weird format
            continue

        # Unique ID for seen check
        job_id = link

        if job_id in seen:
            continue

        # --- Filtering Logic ---
        matched_tier = None
        
        # exact match or partial match check
        for target_company, tier in companies.items():
            # Using word boundary regex for safety (e.g. avoid matching "Eq" in "Equipment")
            if re.search(r"\b" + re.escape(target_company) + r"\b", company.lower()):
                matched_tier = tier
                break
        
        # If we found a company in our list
        if matched_tier:
            print(f"🎯 Match: {company} ({matched_tier})")
            
            # Save to seen
            seen[job_id] = {
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "company": company,
                "position": position
            }
            
            # Send Alert
            msg = f"[{matched_tier}] {position} at {company}\n{link}"
            send_telegram(msg)
            write_log(msg)
            new_count += 1

    save_seen(seen)
    print(f"🏁 Done. Found {new_count} new listings.")

if __name__ == "__main__":
    main()