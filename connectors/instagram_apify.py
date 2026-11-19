"""Instagram hashtag verisi - Apify uzerinden (kendi Instagram hesabimiz kullanilmaz).

Arac: apify/instagram-hashtag-scraper
Gerekli: Apify API anahtari (ucretsiz plan: ayda 5 USD kredi).
"""
from datetime import date

from .apify_run import past_runs_items, run_actor
from .base import Connector, Post, anon


def _int(v) -> int:
    try:
        return max(int(v), 0)          # gizli begenilerde -1 gelebilir
    except (TypeError, ValueError):
        return 0


def _media_type(item: dict) -> str:
    t = str(item.get("type", "")).lower()
    if "video" in t or item.get("videoUrl"):
        return "VIDEO"
    if "sidecar" in t:
        return "CAROUSEL_ALBUM"
    if "image" in t or item.get("displayUrl"):
        return "IMAGE"
    return "TEXT"


def _media_url(item: dict) -> str:
    if item.get("displayUrl"):
        return item["displayUrl"]
    imgs = item.get("images") or []
    if imgs and isinstance(imgs[0], str):
        return imgs[0]
    return ""


def _timestamp(item: dict) -> str:
    ts = item.get("timestamp") or ""
    if not isinstance(ts, str):
        return ""
    ts = ts.strip()
    if ts.endswith(" UTC"):                       # "2026-11-19 00:45:26 UTC"
        ts = ts[:-4].replace(" ", "T") + "+00:00"
    return ts.replace("Z", "+00:00")


def item_to_post(item: dict) -> Post:
    owner = str(item.get("ownerId") or item.get("ownerUsername") or item.get("id") or "")
    short = item.get("shortCode") or ""
    url = item.get("url") or (f"https://www.instagram.com/p/{short}/" if short else "")
    return Post(
        platform="instagram",
        post_id=str(item.get("id") or short or url),
        created_at=_timestamp(item),
        caption=item.get("caption") or "",
        permalink=url,
        media_type=_media_type(item),
        likes=_int(item.get("likesCount")),
        comments=_int(item.get("commentsCount")),
        author_hash=anon(owner) if owner else "",
        media_url=_media_url(item),
    )


def items_to_posts(items, limit=None) -> list:
    posts, seen = [], set()
    for it in items:
        if not isinstance(it, dict) or it.get("error"):
            continue
        p = item_to_post(it)
        if not p.permalink or p.post_id in seen:
            continue
        seen.add(p.post_id)
        posts.append(p)
    return posts if limit is None else posts[: int(limit)]


class InstagramApifyConnector(Connector):
    name = "Instagram (Apify, hesapsiz)"
    notes = [
        "Kendi Instagram hesabimiz kullanilmaz; veri Apify servisi uzerinden cekilir.",
        "Instagram'in gosterdigi gonderiler gelir; hashtag'in tam arsivi degildir. Makalede sinirlilik olarak yazilmali.",
        "Tarih araligi, gelen gonderiler uzerinde uygulanir; eski tarihler havuzda yoksa sonuc az cikabilir.",
        "Ucretsiz planda Apify her aramada en fazla ~30 gonderi verir (Instagram'in ilk sayfasi).",
    ]

    def __init__(self, token: str, results_type: str = "posts", include_history: bool = False,
                 on_progress=None):
        self.token = (token or "").strip()
        self.results_type = results_type
        self.include_history = include_history
        self.on_progress = on_progress

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        tag = hashtag.lstrip("#").strip()
        items = run_actor(self.token, "ig_hashtag", {
            "hashtags": [tag],
            "resultsType": self.results_type,
            "resultsLimit": int(pool_limit),
        }, on_progress=self.on_progress)
        if self.include_history:
            def same_tag(inp):
                tags = [str(t).lstrip("#").strip().lower() for t in (inp.get("hashtags") or [])]
                return tag.lower() in tags
            items = items + past_runs_items(self.token, "ig_hashtag", same_tag)
        # gecmis dahilse havuz siniri yeni cekime uygulanmis olur; birlesik listede tekrarlar atilir
        return items_to_posts(items, None if self.include_history else pool_limit)
