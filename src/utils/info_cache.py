import json
import os
import httpx
from datetime import datetime, timedelta

CACHE_FILE = "/tmp/ipas_news_cache.json"
CACHE_TTL_DAYS = 7
IPAS_API = "https://www.ipas.org.tw/api/proxy/certification/AIAP/news/list"
IPAS_NEWS_URL = "https://www.ipas.org.tw/certification/AIAP/news/{code}"


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


def fetch_and_cache_ipas_news() -> dict:
    r = httpx.get(IPAS_API, timeout=15)
    r.raise_for_status()
    api_data = r.json()
    items = api_data["data"]["datas"]
    news = [
        {
            "title": item["title"],
            "url": IPAS_NEWS_URL.format(code=item["code"]),
            "date": item["publish_date"],
        }
        for item in items
    ]
    data = {"news": news, "fetched_at": datetime.now().isoformat()}
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False)
    return data
