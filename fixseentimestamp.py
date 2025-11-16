import json
from datetime import datetime

SEEN_FILE = "seen.json"

with open(SEEN_FILE, "r") as f:
    seen = json.load(f)

updated = {}
now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

for job_id, data in seen.items():
    # Handle old list-format (string entries)
    if isinstance(data, str):
        updated[job_id] = {
            "timestamp": now,
            "position": "Unknown",
            "company": "Unknown",
            "link": job_id
        }
    # Handle old dict-format missing timestamp
    elif isinstance(data, dict):
        data["timestamp"] = data.get("timestamp", "unknown")
        if data["timestamp"] == "unknown":
            data["timestamp"] = now
        updated[job_id] = data
    else:
        updated[job_id] = {
            "timestamp": now,
            "position": "Unknown",
            "company": "Unknown",
            "link": job_id
        }

with open(SEEN_FILE, "w") as f:
    json.dump(updated, f, indent=2)

print(f"✅ Fixed {len(updated)} entries in {SEEN_FILE}")