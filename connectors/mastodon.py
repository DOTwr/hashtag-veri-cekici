import html
import re
import time
from datetime import date, datetime, timezone

import requests

from .base import Connector, Post, anon

_TAG_RE = re.compile(r"<[^>]+>")
_BR_RE = re.compile(r"<br\s*/?>|</p>", re.I)


def _clean(content: str) -> str:
    text = _BR_RE.sub("\n", content or "")
    text = _TAG_RE.sub("", text)
    return html.unescape(text).strip()


def _media_type(media) -> str:
    kinds = {m.get("type", "") for m in (media or [])}
    if "video" in kinds or "gifv" in kinds:
        return "VIDEO"
    if "image" in kinds:
        return "IMAGE"
    return "TEXT"


def _media_url(media) -> str:
    for m in media or []:
        url = m.get("preview_url") or m.get("url")
        if url:
            return url
    return ""


class MastodonConnector(Connector):
    name = "Mastodon (acik API, giris yok)"
    notes = [
        "Giris/hesap kullanilmaz; hashtag akisi kronolojiktir ve kisisellestirilmez.",
        "Yalnizca secilen sunucunun (instance) gordugu gonderiler gelir; tum Mastodon agi degildir.",
        "Bazi sunucular girissiz hashtag erisimini kapatmistir; o durumda baska sunucu secilmelidir.",
    ]

    def __init__(self, instance: str = "mastodon.social", local_only: bool = False):
        inst = instance.strip().lower()
        inst = re.sub(r"^https?://", "", inst).strip("/")
        self.instance = inst or "mastodon.social"
        self.local_only = local_only

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        tag = hashtag.lstrip("#").strip()
        url = f"https://{self.instance}/api/v1/timelines/tag/{tag}"
        params = {"limit": 40}
        if self.local_only:
            params["local"] = "true"

        posts, seen = [], set()
        for _ in range(1000):                      # sonsuz dongu korumasi
            try:
                r = requests.get(url, params=params, timeout=30)
            except requests.RequestException:
                raise RuntimeError(
                    f"{self.instance} sunucusuna baglanilamadi. Internet baglantini kontrol et "
                    "veya baska bir sunucu dene (ornek: mastodon.online, mstdn.social).")
            if r.status_code in (401, 403):
                raise RuntimeError(
                    f"{self.instance} girissiz hashtag erisimini kapatmis. Baska bir sunucu dene "
                    "(ornek: mastodon.social, mastodon.online, mstdn.social).")
            if r.status_code == 429:
                raise RuntimeError("Mastodon istek limiti doldu; birkac dakika bekleyip tekrar dene.")
            if r.status_code != 200:
                raise RuntimeError(f"Mastodon hatasi ({r.status_code}): {r.text[:200]}")
            batch = r.json()
            if not batch:
                break

            oldest = None
            for s in batch:
                sid = str(s.get("id", ""))
                if not sid or sid in seen:
                    continue
                seen.add(sid)
                try:
                    created = datetime.fromisoformat(s["created_at"].replace("Z", "+00:00"))
                except (KeyError, ValueError):
                    continue
                if created.tzinfo is None:
                    created = created.replace(tzinfo=timezone.utc)
                oldest = created if oldest is None else min(oldest, created)
                if not (start <= created.astimezone(timezone.utc).date() <= end):
                    continue
                acc = s.get("account") or {}
                posts.append(Post(
                    platform="mastodon",
                    post_id=f"{self.instance}:{sid}",
                    created_at=created.isoformat(),
                    caption=_clean(s.get("content", "")),
                    permalink=s.get("url") or s.get("uri") or "",
                    media_type=_media_type(s.get("media_attachments")),
                    likes=s.get("favourites_count", 0) or 0,
                    comments=s.get("replies_count", 0) or 0,
                    author_hash=anon(str(acc.get("id", acc.get("acct", sid)))),
                    media_url=_media_url(s.get("media_attachments")),
                ))
                if len(posts) >= pool_limit:
                    return posts

            if oldest is None or oldest.astimezone(timezone.utc).date() < start:
                break                                # baslangic tarihinin oncesine ulastik
            params["max_id"] = str(min(int(str(s.get("id"))) for s in batch if str(s.get("id", "")).isdigit()))
            time.sleep(0.3)                          # sunucuya nazik ol
        return posts
