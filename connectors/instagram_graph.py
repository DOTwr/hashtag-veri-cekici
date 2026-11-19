import hashlib
from datetime import date, datetime

import requests

from .base import Connector, Post

API = "https://graph.facebook.com/v21.0"
FIELDS = "id,caption,media_type,permalink,timestamp,like_count,comments_count"


class InstagramGraphConnector(Connector):
    name = "Instagram Graph API (resmi)"
    notes = [
        "'Son gonderiler' yalnizca son 24 saati verir; keyfi gecmis tarih araligi bu API ile alinamaz.",
        "'En populer' secenegi Instagram'in kendi algoritmik siralamasidir (algoritmadan etkilenmis).",
        "Haftada sinirli sayida benzersiz hashtag sorgulanabilir.",
    ]

    def __init__(self, user_id: str, access_token: str, feed: str = "recent_media"):
        self.user_id = user_id
        self.token = access_token
        self.feed = feed  # "recent_media" veya "top_media"

    def _get(self, url, params):
        r = requests.get(url, params=params, timeout=30)
        data = r.json()
        if r.status_code != 200 or "error" in data:
            msg = data.get("error", {}).get("message", r.text)
            raise RuntimeError(f"Instagram API hatasi: {msg}")
        return data

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        tag = hashtag.lstrip("#").strip()
        h = self._get(f"{API}/ig_hashtag_search",
                      {"user_id": self.user_id, "q": tag, "access_token": self.token})
        hid = h["data"][0]["id"]

        url = f"{API}/{hid}/{self.feed}"
        params = {"user_id": self.user_id, "fields": FIELDS,
                  "limit": 50, "access_token": self.token}
        posts = []
        while url and len(posts) < pool_limit:
            data = self._get(url, params)
            for m in data.get("data", []):
                ts = m.get("timestamp", "")
                try:
                    created = datetime.strptime(ts, "%Y-%m-%dT%H:%M:%S%z").isoformat()
                except ValueError:
                    created = ts
                posts.append(Post(
                    platform="instagram",
                    post_id=m["id"],
                    created_at=created,
                    caption=m.get("caption", "") or "",
                    permalink=m.get("permalink", ""),
                    media_type=m.get("media_type", ""),
                    likes=m.get("like_count", 0) or 0,
                    comments=m.get("comments_count", 0) or 0,
                    author_hash=hashlib.sha256(m["id"].encode()).hexdigest()[:10],
                ))
            url = data.get("paging", {}).get("next")
            params = None  # "next" linki parametreleri zaten icerir
        return posts[:pool_limit]
