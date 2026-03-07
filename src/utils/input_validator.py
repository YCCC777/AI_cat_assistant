"""
輸入驗證工具：短網址封鎖、URL allowlist、Prompt Injection 偵測。
"""
import re
from urllib.parse import urlparse

# ── 短網址 domain 清單（一律封鎖，不論目的地）──────────────────────────
SHORT_URL_DOMAINS = {
    "bit.ly", "tinyurl.com", "t.co", "goo.gl", "ow.ly", "short.io",
    "rb.gy", "is.gd", "buff.ly", "tiny.cc", "lnkd.in", "fb.me",
    "shorturl.at", "cutt.ly", "snip.ly", "bl.ink", "reurl.cc",
    "pse.is", "lihi.io", "lihi1.com", "lihi2.com", "lihi3.cc",
    "ppt.cc", "0rz.tw",
}

# ── 允許的 URL domain（精確或 TLD 後綴）───────────────────────────────
ALLOWED_URL_DOMAINS = {
    # 課程報名平台
    "accupass.com", "kktix.cc", "kktix.com", "eventbrite.com",
    "iwilllearn.com.tw",
    # 線上會議
    "meet.google.com", "zoom.us", "webex.com", "meet.jit.si",
    "teams.microsoft.com", "teams.live.com",
    # 官方與教育機構（精確 domain）
    "hrd.gov.tw", "ipas.org.tw", "ntu.edu.tw", "ntust.edu.tw",
    "ntnu.edu.tw", "nctu.edu.tw", "csie.ntu.edu.tw",
    # 社群活動頁
    "facebook.com", "fb.com",
    # 影音（可選）
    "youtube.com", "youtu.be",
}

# TLD 後綴白名單（結尾符合即通過）
ALLOWED_TLD_SUFFIXES = (".gov.tw", ".edu.tw", ".mil.tw")

# ── Prompt Injection 特徵（正規表達式）────────────────────────────────
_INJECTION_PATTERNS = [
    # 中文身分覆寫
    r"忘(掉|記|了).{0,20}(設定|指令|身分|角色|以前|之前)",
    r"(你現在是|你是一個).{0,30}(而不是|不再|忘掉|忘記)",
    r"(現在開始|從現在起).{0,20}(只|不|改|變|說|用|當)",
    r"新(的)?指令",
    # 英文 jailbreak
    r"(?i)(ignore|forget|disregard|override)\s+(all\s+)?(previous|prior|above|your|the)\s+(instruction|prompt|rule|setting|directive)",
    r"(?i)(act\s+as|pretend\s+(to\s+be|you\s+are)|assume\s+(the\s+role|you\s+are))",
    r"(?i)(jailbreak|dan\s+mode|do\s+anything\s+now)",
    r"(?i)(you\s+are\s+now|from\s+now\s+on\s+you)",
    # 系統層注入
    r"(?i)(system\s*:|<\s*system\s*>|\[system\]|##\s*system|###\s*instruction)",
    r"(?i)(new\s+instruction|prompt\s+injection|ignore\s+above)",
    # XML/Markdown 注入
    r"<\s*(system|instruction|prompt|role)\s*>",
    r"```\s*(system|instruction|prompt)",
]
_COMPILED_PATTERNS = [re.compile(p) for p in _INJECTION_PATTERNS]

# URL 提取 regex
_URL_RE = re.compile(r"https?://[^\s\"'<>]+")


def _get_domain(url: str) -> str:
    """從 URL 取出 netloc（小寫，去除 www. 前綴）。"""
    try:
        netloc = urlparse(url).netloc.lower()
        return netloc.removeprefix("www.")
    except Exception:
        return ""


def is_short_url(url: str) -> bool:
    return _get_domain(url) in SHORT_URL_DOMAINS


def is_allowed_url(url: str) -> bool:
    domain = _get_domain(url)
    if not domain:
        return False
    if domain in ALLOWED_URL_DOMAINS:
        return True
    if any(domain.endswith(suffix) for suffix in ALLOWED_TLD_SUFFIXES):
        return True
    return False


def sanitize_url(url: str | None) -> str | None:
    """
    回傳清理後的 URL，若為短網址或不在 allowlist 則回傳 None。
    """
    if not url:
        return None
    if is_short_url(url):
        return None
    if not is_allowed_url(url):
        return None
    return url


def is_prompt_injection(text: str) -> bool:
    """
    偵測文字是否含有 Prompt Injection 特徵。
    """
    for pattern in _COMPILED_PATTERNS:
        if pattern.search(text):
            return True
    return False


def contains_short_url(text: str) -> bool:
    """
    偵測文字中是否含有短網址。
    """
    for url in _URL_RE.findall(text):
        if is_short_url(url):
            return True
    return False


def validate_message(text: str) -> tuple[bool, str]:
    """
    綜合驗證訊息，回傳 (is_valid, reject_reason)。
    """
    if is_prompt_injection(text):
        return False, "injection"
    if contains_short_url(text):
        return False, "short_url"
    return True, ""
