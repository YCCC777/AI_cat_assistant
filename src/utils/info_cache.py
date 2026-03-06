import json
import os
from datetime import datetime, timedelta

CACHE_FILE = "/tmp/ai_info_cache.json"
CACHE_TTL_DAYS = 7


def get_cached_info() -> dict | None:
    if not os.path.exists(CACHE_FILE):
        return None
    try:
        with open(CACHE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
        fetched_at = datetime.fromisoformat(data["fetched_at"])
        if datetime.now() - fetched_at < timedelta(days=CACHE_TTL_DAYS):
            return data
        return None
    except Exception:
        return None


def save_cache(content: str):
    data = {
        "content": content,
        "fetched_at": datetime.now().isoformat()
    }
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
