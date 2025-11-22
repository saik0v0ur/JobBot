import pandas as pd
import requests
import json
import os
import sys

# Configuration
# The shared view ID from your link
AIRTABLE_CSV_URL = "https://airtable.com/shrOTtndhc6HSgnYb/csv"
SEEN_JOBS_FILE = "seen_jobs.json"
COMPANIES_FILE = "companies.txt"

# Telegram Secrets (Set these in GitHub Secrets)
BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def send_telegram_message(message):
    if not BOT_TOKEN or not CHAT_ID:
        print("Error: Telegram credentials not found.")
        return
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": message,
        "parse_mode": "Markdown"
    }
    requests.post(url, json=payload)

def load_seen_jobs():
    if os.path.exists(SEEN_JOBS_FILE):
        with open(SEEN_JOBS_FILE, 'r') as f:
            return set(json.load(f))
    return set()

def save_seen_jobs(seen_jobs):
    with open(SEEN_JOBS_FILE, 'w') as f:
        json.dump(list(seen_jobs), f)

def get_target_companies():
    """
    Returns a dictionary where Key = Company Name (lowercase) and Value = Tier
    Example: {'google': 'Tier 1', 'startup': 'Tier 3'}
    """
    companies = {}
    if os.path.exists(COMPANIES_FILE):
        with open(COMPANIES_FILE, 'r') as f:
            for line in f:
                parts = line.strip().split('|')
                # Ensure line has both name and tier
                if len(parts) >= 2:
                    name = parts[0].strip().lower()
                    tier = parts[1].strip()
                    companies[name] = tier
    return companies

def main():
    print("Fetching data from Airtable...")
    try:
        df = pd.read_csv(AIRTABLE_CSV_URL)
    except Exception as e:
        print(f"Failed to fetch CSV. Error: {e}")
        sys.exit(1)

    df.columns = df.columns.str.strip()
    
    # Identify key columns
    company_col = next((c for c in df.columns if 'Company' in c), None)
    role_col = next((c for c in df.columns if 'Role' in c or 'Title' in c), None)
    link_col = next((c for c in df.columns if 'Link' in c or 'Apply' in c or 'URL' in c), None)

    if not company_col:
        print(f"Could not find a 'Company' column. Found: {df.columns.tolist()}")
        sys.exit(1)

    # Load targets as a dictionary
    target_companies = get_target_companies()
    seen_jobs = load_seen_jobs()
    new_jobs_found = []

    print(f"Checking {len(df)} rows against {len(target_companies)} target companies...")

    for _, row in df.iterrows():
        company_name = str(row[company_col]).strip()
        company_name_lower = company_name.lower()
        
        # Find the matching tier if the company is in our target list
        # We check if any target key is a substring of the Airtable company name
        matched_tier = next(
            (tier for target, tier in target_companies.items() if target in company_name_lower), 
            None
        )
        
        if matched_tier:
            job_id = f"{company_name}-{row.get(role_col, 'N/A')}-{row.get(link_col, 'N/A')}"
            
            if job_id not in seen_jobs:
                job_link = row.get(link_col, "No Link")
                role = row.get(role_col, "N/A")
                
                msg = (
                    f"🚨 **New Job Alert!**\n\n"
                    f"🏢 **Company:** {company_name}\n"
                    f"🏆 **Tier:** {matched_tier}\n"
                    f"👨‍💻 **Role:** {role}\n"
                    f"🔗 [Apply Here]({job_link})"
                )
                
                print(f"Sending alert for: {company_name} ({matched_tier})")
                send_telegram_message(msg)
                seen_jobs.add(job_id)
                new_jobs_found.append(job_id)

    if new_jobs_found:
        save_seen_jobs(seen_jobs)
        print(f"Sent {len(new_jobs_found)} new alerts.")
    else:
        print("No new matching jobs found.")

if __name__ == "__main__":
    main()