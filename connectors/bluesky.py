from datetime import date, datetime, time, timedelta, timezone

import requests

from .base import Connector, Post, anon

PDS = "https://bsky.social"


class BlueskyConnector(Connector):
    name = "Bluesky (acik API)"
    notes = [
        "Havuz 'latest' (kronolojik) siralamayla cekilir; algoritmik siralama kullanilmaz.",
        "Bluesky kitlesi Instagram'dan farklidir; sonuclar platformlar arasi genellenemez.",
    ]

    def __init__(self, handle: str, app_password: str):
        self.handle = handle.strip().lstrip("@")
        self.app_password = app_password.strip()

    def _login(self) -> str:
        r = requests.post(
            f"{PDS}/xrpc/com.atproto.server.createSession",
            json={"identifier": self.handle, "password": self.app_password},
            timeout=30,
        )
        if r.status_code != 200:
            raise RuntimeError("Bluesky girisi basarisiz: handle veya App Password hatali.")
        return r.json()["accessJwt"]

    @staticmethod
    def _media_type(post: dict) -> str:
        t = (post.get("embed") or {}).get("$type", "")
        if "images" in t:
            return "IMAGE"
        if "video" in t:
            return "VIDEO"
        if "external" in t:
            return "LINK"
        return "TEXT"

    @staticmethod
    def _media_url(post: dict) -> str:
        embed = post.get("embed") or {}
        imgs = embed.get("images") or (embed.get("media") or {}).get("images") or []
        if imgs:
            return imgs[0].get("thumb") or imgs[0].get("fullsize") or ""
        return embed.get("thumbnail", "") or ""

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        tag = hashtag.lstrip("#").strip()
        token = self._login()
        headers = {"Authorization": f"Bearer {token}"}
        since = datetime.combine(start, time.min, tzinfo=timezone.utc)
        until = datetime.combine(end + timedelta(days=1), time.min, tzinfo=timezone.utc)

        params = {
            "q": tag, "tag": tag, "sort": "latest", "limit": 100,
            "since": since.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "until": until.strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        posts = []
        while len(posts) < pool_limit:
            r = requests.get(f"{PDS}/xrpc/app.bsky.feed.searchPosts",
                             params=params, headers=headers, timeout=30)
            if r.status_code == 429:
                raise RuntimeError("Bluesky istek limiti doldu; biraz bekleyip tekrar dene.")
            if r.status_code != 200:
                raise RuntimeError(f"Bluesky arama hatasi ({r.status_code}): {r.text[:200]}")
            data = r.json()
            batch = data.get("posts", [])
            for p in batch:
                rec = p.get("record", {})
                handle = p.get("author", {}).get("handle", "")
                rkey = p.get("uri", "").rsplit("/", 1)[-1]
                posts.append(Post(
                    platform="bluesky",
                    post_id=p.get("uri", ""),
                    created_at=(rec.get("createdAt") or p.get("indexedAt", "")).replace("Z", "+00:00"),
                    caption=rec.get("text", "") or "",
                    permalink=f"https://bsky.app/profile/{handle}/post/{rkey}",
                    media_type=self._media_type(p),
                    likes=p.get("likeCount", 0) or 0,
                    comments=p.get("replyCount", 0) or 0,
                    author_hash=anon(p.get("author", {}).get("did", handle)),
                    media_url=self._media_url(p),
                ))
            cursor = data.get("cursor")
            if not cursor or not batch:
                break
            params["cursor"] = cursor
        return posts[:pool_limit]
