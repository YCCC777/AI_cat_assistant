"""
iPAS 考試日期管理。
- 先用 hard-code 資料（115年4場）
- 每年年份不符時自動嘗試從官網爬蟲更新
- 快取至 /tmp/ipas_exam_dates_cache.json
"""
import json
import logging
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

CACHE_PATH = Path("/tmp/ipas_exam_dates_cache.json")
SCRAPE_URL = "https://ipd.nat.gov.tw/ipas/certification/AIAP/exam-info"

# Hard-code 資料，key 為民國年字串
EXAM_SCHEDULE: dict[str, dict[str, list[tuple[str, str]]]] = {
    "iPAS AI應用規劃師（初級）": {
        "115": [
            ("第一場 3/21", "2026-03-21"),
            ("第二場 5/16", "2026-05-16"),
            ("第三場 8/15", "2026-08-15"),
            ("第四場 11/7", "2026-11-07"),
        ]
    }
}

EXAM_KEY_MAP = {
    "iPAS初級": "iPAS AI應用規劃師（初級）",
}


def _roc_year() -> str:
    """取得當前民國年（字串）"""
    return str(datetime.now().year - 1911)


def _load_cache() -> dict | None:
    try:
        if CACHE_PATH.exists():
            return json.loads(CACHE_PATH.read_text(encoding="utf-8"))
    except Exception:
        pass
    return None


def _save_cache(data: dict):
    try:
        CACHE_PATH.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        logger.warning(f"exam_dates 快取寫入失敗: {e}")


def fetch_and_cache_exam_dates() -> dict[str, list[tuple[str, str]]]:
    """
    從官網爬取考試日期，成功則寫快取並回傳，失敗則拋出例外。
    回傳格式：{ "iPAS AI應用規劃師（初級）": [("第一場 3/21", "2026-03-21"), ...] }
    """
    import urllib.request
    from html.parser import HTMLParser

    class _DateParser(HTMLParser):
        def __init__(self):
            super().__init__()
            self.dates: list[str] = []
            self._capture = False

        def handle_starttag(self, tag, attrs):
            attrs_dict = dict(attrs)
            # 嘗試抓含日期的 td/div/span
            if tag in ("td", "span", "div", "p"):
                self._capture = True

        def handle_data(self, data):
            data = data.strip()
            if self._capture and data:
                # 找含民國年格式的字串，例如 "115年03月21日" 或 "115/03/21"
                import re
                if re.search(r"1\d{2}[年/]\d{1,2}[月/]\d{1,2}", data):
                    self.dates.append(data)
            self._capture = False

    req = urllib.request.Request(SCRAPE_URL, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        html = resp.read().decode("utf-8", errors="ignore")

    parser = _DateParser()
    parser.feed(html)

    import re
    dates: list[tuple[str, str]] = []
    for raw in parser.dates:
        m = re.search(r"(1\d{2})[年/](\d{1,2})[月/](\d{1,2})", raw)
        if m:
            roc, month, day = m.groups()
            year = int(roc) + 1911
            iso = f"{year}-{int(month):02d}-{int(day):02d}"
            label = f"{month}/{day}"
            dates.append((label, iso))

    if not dates:
        raise ValueError("爬蟲未找到任何日期")

    # 補上場次標籤
    labeled = [(f"第{i+1}場 {label}", iso) for i, (label, iso) in enumerate(dates[:4])]
    result = {"iPAS AI應用規劃師（初級）": labeled}
    _save_cache({"year": _roc_year(), **result})
    logger.info(f"exam_dates 爬蟲更新成功，共 {len(labeled)} 場")
    return result


def get_exam_dates(exam_name: str) -> list[tuple[str, str]]:
    """
    取得指定考試的日期列表。
    優先用快取，年份不符時嘗試爬蟲，失敗 fallback hard-code。
    """
    roc = _roc_year()
    cache = _load_cache()
    if cache and cache.get("year") == roc and exam_name in cache:
        return [tuple(x) for x in cache[exam_name]]

    # 快取過期或不存在，嘗試爬蟲
    try:
        result = fetch_and_cache_exam_dates()
        return result.get(exam_name, [])
    except Exception as e:
        logger.warning(f"exam_dates 爬蟲失敗，使用 hard-code: {e}")

    # Fallback：hard-code
    return EXAM_SCHEDULE.get(exam_name, {}).get(roc, [])


def get_all_exam_names() -> list[str]:
    """回傳目前支援的考試名稱列表。"""
    return list(EXAM_SCHEDULE.keys())
