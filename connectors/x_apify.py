"""X (Twitter) hashtag verisi - Apify uzerinden (kendi X hesabimiz kullanilmaz).

Arac: xquik/x-tweet-scraper (arama modu; hashtag + tarih araligi).
"""
from datetime import date, datetime, timedelta

from .apify_run import run_actor
from .base import Connector, Post, anon


def _int(v) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0


def _iso(ts) -> str:
    if not isinstance(ts, str) or not ts.strip():
        return ""
    try:
        return datetime.strptime(ts.strip(), "%a %b %d %H:%M:%S %z %Y").isoformat()
    except ValueError:
        return ts.replace("Z", "+00:00")


def anon_x_url(tweet_id: str) -> str:
    """Kullanici adini icermeyen, calisan X linki."""
    return f"https://x.com/i/web/status/{tweet_id}" if tweet_id else ""


def item_to_post(item: dict) -> Post:
    tid = str(item.get("id") or "")
    vids = item.get("videoUrls") or []
    imgs = [u for u in (item.get("imageUrls") or item.get("mediaUrls") or []) if isinstance(u, str)]
    kind = "VIDEO" if vids else ("IMAGE" if imgs else "TEXT")
    aid = str(item.get("authorId") or (item.get("author") or {}).get("id") or "")
    return Post(
        platform="x",
        post_id=tid,
        created_at=_iso(item.get("createdAt")),
        caption=item.get("text") or item.get("fullText") or "",
        permalink=anon_x_url(tid),
        media_type=kind,
        likes=_int(item.get("likeCount")),
        comments=_int(item.get("replyCount")),
        author_hash=anon(aid) if aid else "",
        media_url=imgs[0] if imgs else "",
    )


class XApifyConnector(Connector):
    name = "X (Apify, hesapsiz)"
    notes = [
        "Kendi X hesabimiz kullanilmaz; veri Apify servisi uzerinden X aramasiyla cekilir.",
        "Arama 'en yeni' sirasiyla yapilir; X'in arama sonuclari tam arsiv olmayabilir.",
        "Linkler kullanici adi icermeyecek bicimde (x.com/i/web/status/...) verilir.",
    ]

    def __init__(self, token: str, on_progress=None):
        self.token = (token or "").strip()
        self.on_progress = on_progress

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        tag = hashtag.lstrip("#").strip()
        items = run_actor(self.token, "x_posts", {
            "searchTerms": [f"#{tag}"],
            "since": start.isoformat(),
            "until": (end + timedelta(days=1)).isoformat(),   # 'until' haric oldugu icin +1 gun
            "queryType": "Latest",
            "maxItems": int(pool_limit),
            "outputVariant": "rich", "fieldStyle": "camelCase", "outputPreset": "flat",
        }, on_progress=self.on_progress)
        posts, seen = [], set()
        for it in items:
            if not it.get("id") or not (it.get("text") or it.get("fullText")):
                continue          # durum satirlari vb.
            p = item_to_post(it)
            if p.post_id in seen:
                continue
            seen.add(p.post_id)
            posts.append(p)
        return posts[: int(pool_limit)]
