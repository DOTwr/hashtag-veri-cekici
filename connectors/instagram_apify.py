"""Instagram hashtag verisi - Apify uzerinden (kendi Instagram hesabimiz kullanilmaz).

Arac: apify/instagram-hashtag-scraper
Gerekli: Apify API anahtari (ucretsiz plan: ayda 5 USD kredi).
"""
from datetime import date

import requests

from .base import Connector, Post, anon

ACTOR = "apify~instagram-hashtag-scraper"
ENDPOINT = f"https://api.apify.com/v2/acts/{ACTOR}/run-sync-get-dataset-items"


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
    return ts.replace("Z", "+00:00") if isinstance(ts, str) else ""


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


class InstagramApifyConnector(Connector):
    name = "Instagram (Apify, hesapsiz)"
    notes = [
        "Kendi Instagram hesabimiz kullanilmaz; veri Apify servisi uzerinden cekilir.",
        "Instagram'in gosterdigi gonderiler gelir; hashtag'in tam arsivi degildir. Makalede sinirlilik olarak yazilmali.",
        "Tarih araligi, gelen gonderiler uzerinde uygulanir; eski tarihler havuzda yoksa sonuc az cikabilir.",
        "Ucretsiz planda Apify her aramada en fazla ~30 gonderi verir (Instagram'in ilk sayfasi).",
    ]

    def __init__(self, token: str, results_type: str = "posts"):
        self.token = (token or "").strip()
        self.results_type = results_type

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        if not self.token:
            raise RuntimeError("Apify API anahtari gerekli.")
        tag = hashtag.lstrip("#").strip()
        body = {
            "hashtags": [tag],
            "resultsType": self.results_type,
            "resultsLimit": int(pool_limit),
        }
        try:
            r = requests.post(
                ENDPOINT,
                params={"timeout": 280},
                headers={"Authorization": f"Bearer {self.token}"},
                json=body,
                timeout=300,
            )
        except requests.Timeout:
            raise RuntimeError("Apify yanit vermedi (zaman asimi). Daha kucuk bir gonderi sayisiyla tekrar dene.")
        except requests.RequestException:
            raise RuntimeError("Apify'a baglanilamadi. Internet baglantini kontrol et.")

        if r.status_code == 401:
            raise RuntimeError("Apify API anahtari gecersiz. Settings > API & Integrations sayfasindan kontrol et.")
        if r.status_code == 402:
            raise RuntimeError("Apify ucretsiz kredisi bu ay doldu. Ay basinda yenilenir.")
        if r.status_code == 408:
            raise RuntimeError("Apify islemi zamaninda bitmedi. Daha kucuk bir gonderi sayisiyla tekrar dene.")
        if r.status_code not in (200, 201):
            raise RuntimeError(f"Apify hatasi ({r.status_code}): {r.text[:200]}")

        try:
            items = r.json()
        except ValueError:
            raise RuntimeError("Apify'dan anlasilmayan bir yanit geldi.")
        if not isinstance(items, list):
            raise RuntimeError(f"Apify beklenmeyen yanit: {str(items)[:200]}")

        posts, seen = [], set()
        for it in items:
            if not isinstance(it, dict) or it.get("error"):
                continue
            p = item_to_post(it)
            if not p.permalink or p.post_id in seen:
                continue
            seen.add(p.post_id)
            posts.append(p)
        return posts[: int(pool_limit)]
