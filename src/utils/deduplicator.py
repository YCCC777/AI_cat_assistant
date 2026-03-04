import hashlib
from typing import Set

class Deduplicator:
    """
    負責攔截完全重複的訊息，以節省 Token 成本。
    """
    def __init__(self, cache_size: int = 1000):
        # 簡單的 Hash 集合，用於判斷內容是否重複
        self.hashes: Set[str] = set()
        self.cache_size = cache_size

    def is_duplicate(self, content: str) -> bool:
        """
        將內容雜湊後比對是否重複。
        """
        # 移除多餘空白與換行再進行 Hash
        normalized_content = "".join(content.split())
        content_hash = hashlib.md5(normalized_content.encode('utf-8')).hexdigest()
        
        if content_hash in self.hashes:
            return True
        
        # 維護快取大小
        if len(self.hashes) >= self.cache_size:
            # 如果快取滿了，清空一半 (簡單的機制)
            self.hashes = set(list(self.hashes)[len(self.hashes)//2:])
            
        self.hashes.add(content_hash)
        return False

# 單例模式實例
deduplicator = Deduplicator()
