import requests
import json
import os
import re

# ----------------------------
# CONFIG
# ----------------------------
QUERY = "Software Engineering Intern"
URL = f"https://api.jobright.ai/jobs?query={QUERY.replace(' ', '%20')}&sort=recent"
STATE_FILE = "seen.json"
COMPANY_FILE = "companies.txt"

TELEGRAM_TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

# ----------------------------
# HELPERS
# ----------------------------
def load_seen():
    if os.path.exists(STATE_FILE):
        with open(STATE_FILE, "r") as f:
            return set(json.load(f))
    return set()

def save_seen(seen):
    with open(STATE_FILE, "w") as f:
        json.dump(list(seen), f)

def load_companies():
    comp = {}
    if os.path.exists(COMPANY_FILE):
        with open(COMPANY_FILE, "r") as f:
            for line in f:
                if "|" in line:
                    name, tier = line.strip().split("|", 1)
                    comp[name.lower()] = tier
    return comp

def send_telegram(msg):
    if not TELEGRAM_TOKEN or not CHAT_ID:
        print("Telegram not configured.")
        return
    try:
        requests.post(
            f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage",
            data={
                "chat_id": CHAT_ID,
                "text": msg,
                "disable_web_page_preview": True
            },
            timeout=15
        )
    except Exception as e:
        print("Telegram send failed:", e)

# ----------------------------
# TITLE MATCHING LOGIC
# ----------------------------
def has_all_keywords(title):
    """
    Return True if title includes software plus engineer or engineering
    plus intern or internship, in any order, ignoring punctuation.
    """
    text = re.sub(r"[^a-z\s]", " ", title.lower())
    tokens = text.split()

    def contains_root(root):
        return any(token.startswith(root) for token in tokens)

    return (
        contains_root("software")
        and contains_root("engineer")
        and contains_root("intern")
    )

# ----------------------------
# CORE
# ----------------------------
def fetch_jobs():
    try:
        resp = requests.get(URL, timeout=15)
        resp.raise_for_status()
        data = resp.json()
        return data.get("results", [])
    except Exception as e:
        print("Fetch failed:", e)
        return []

def main():
    seen = load_seen()
    companies = load_companies()
    jobs = fetch_jobs()
    new_jobs = []

    print(f"Loaded {len(seen)} seen jobs")
    print(f"Loaded {len(companies)} companies from {COMPANY_FILE}")

    for job in jobs:
        title = job.get("title", "").lower()
        company_name = job.get("company_name", "")
        company = company_name.lower()
        url = job.get("job_url", "")

        if not title or not url or not company_name:
            continue

        if not has_all_keywords(title):
            continue

        if company not in companies:
            continue

        if url in seen:
            continue

        seen.add(url)
        tier = companies[company]
        msg = (
            f"[{tier}] {job['title']} at {company_name}\n"
            f"{job.get('location', 'Location not listed')}\n"
            f"{url}"
        )
        send_telegram(msg)
        print("Sent:", msg)
        new_jobs.append(job)

    save_seen(seen)
    print(f"Checked {len(jobs)} jobs, found {len(new_jobs)} new matches.")

if __name__ == "__main__":
    main()
