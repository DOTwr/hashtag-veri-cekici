"""Gonderi linklerinden (Instagram / X) gonderi bilgisi ve yorum cekme.

Kendi hesabimiz kullanilmaz; veri Apify araclari uzerinden gelir.
Kullanici kimlikleri anonim kod olarak tutulur.
"""
import re
from dataclasses import dataclass, field
from datetime import datetime

from connectors.apify_run import run_actor
from connectors.base import anon
from connectors.x_apify import anon_x_url

_IG_RE = re.compile(r"(?:https?://)?(?:www\.|m\.)?instagram\.com/(?:[A-Za-z0-9_.]+/)?(p|reel|reels|tv)/([A-Za-z0-9_-]+)", re.I)
_X_RE = re.compile(r"(?:https?://)?(?:www\.|mobile\.)?(?:x|twitter)\.com/([A-Za-z0-9_]+)/status(?:es)?/(\d+)", re.I)
_MENTION_RE = re.compile(r"@[A-Za-z0-9_.]+")

MAX_LINKS = 100


# ---------------------------------------------------------------- linkler
@dataclass
class Link:
    platform: str     # instagram | x
    url: str          # normallestirilmis link
    key: str          # instagram shortcode veya X gonderi id


def parse_links(text: str):
    """Metindeki Instagram/X gonderi linklerini bulur. (gecerli, gecersiz_satirlar) dondurur."""
    links, seen, bad = [], set(), []
    for line in (text or "").splitlines():
        line = line.strip()
        if not line:
            continue
        found = []                     # (konum, Link) - satirdaki sirayla
        for m in _IG_RE.finditer(line):
            kind, code = m.group(1).lower(), m.group(2)
            path = "reel" if kind in ("reel", "reels") else ("tv" if kind == "tv" else "p")
            found.append((m.start(), ("instagram", code),
                          Link("instagram", f"https://www.instagram.com/{path}/{code}/", code)))
        for m in _X_RE.finditer(line):
            user, tid = m.group(1), m.group(2)
            found.append((m.start(), ("x", tid), Link("x", f"https://x.com/{user}/status/{tid}", tid)))
        if not found:
            bad.append(line)
            continue
        for _, key, link in sorted(found, key=lambda f: f[0]):
            if key not in seen:
                seen.add(key)
                links.append(link)
    return links, bad


def mask_mentions(text: str) -> str:
    """Metindeki @kullaniciadi ifadelerini gizler (anonimlik icin)."""
    return _MENTION_RE.sub("@kullanici", text or "")


# ---------------------------------------------------------------- yardimcilar
def _int(v) -> int:
    try:
        return max(int(v), 0)
    except (TypeError, ValueError):
        return 0


def _iso_ig(ts) -> str:
    if not isinstance(ts, str) or not ts.strip():
        return ""
    ts = ts.strip()
    if ts.endswith(" UTC"):
        ts = ts[:-4].replace(" ", "T") + "+00:00"
    return ts.replace("Z", "+00:00")


def _iso_x(ts) -> str:
    """'Thu Nov 19 15:19:14 +0000 2026' -> ISO."""
    if not isinstance(ts, str) or not ts.strip():
        return ""
    try:
        return datetime.strptime(ts.strip(), "%a %b %d %H:%M:%S %z %Y").isoformat()
    except ValueError:
        return ts.replace("Z", "+00:00")


def _shortcode(url: str) -> str:
    m = _IG_RE.search(url or "")
    return m.group(2) if m else ""


# ---------------------------------------------------------------- veri yapilari
@dataclass
class PostDetail:
    platform: str
    url: str
    key: str
    found: bool = False
    created_at: str = ""
    text: str = ""
    likes: int = 0
    comments: int = 0
    shares: int = 0          # X: repost
    quotes: int = 0          # X: alinti
    views: int = 0           # X: goruntulenme, IG: video izlenme
    media_type: str = ""
    media_url: str = ""
    author_hash: str = ""

    @property
    def engagement(self) -> int:
        return self.likes + self.comments + self.shares + self.quotes


@dataclass
class Comment:
    platform: str
    post_url: str
    comment_id: str
    created_at: str
    text: str
    likes: int
    replies: int
    depth: int               # 1 = gonderiye dogrudan yorum, 2+ = yoruma yanit
    author_hash: str
    url: str = ""


# ---------------------------------------------------------------- Instagram
def _ig_media(item: dict):
    t = str(item.get("type", "")).lower()
    kind = "VIDEO" if ("video" in t or item.get("videoUrl")) else (
        "CAROUSEL_ALBUM" if "sidecar" in t else "IMAGE")
    url = item.get("displayUrl") or ""
    if not url:
        imgs = item.get("images") or []
        if imgs and isinstance(imgs[0], str):
            url = imgs[0]
    return kind, url


def ig_item_to_detail(item: dict, link: Link) -> PostDetail:
    kind, murl = _ig_media(item)
    owner = str(item.get("ownerId") or item.get("ownerUsername") or "")
    return PostDetail(
        platform="instagram", url=link.url, key=link.key, found=True,
        created_at=_iso_ig(item.get("timestamp")),
        text=item.get("caption") or "",
        likes=_int(item.get("likesCount")), comments=_int(item.get("commentsCount")),
        views=_int(item.get("videoPlayCount") or item.get("videoViewCount")),
        media_type=kind, media_url=murl,
        author_hash=anon(owner) if owner else "",
    )


def ig_item_to_comment(item: dict) -> Comment:
    owner = item.get("owner") if isinstance(item.get("owner"), dict) else {}
    oid = str(owner.get("id") or item.get("ownerUsername") or item.get("id") or "")
    return Comment(
        platform="instagram",
        post_url=item.get("postUrl") or "",
        comment_id=str(item.get("id") or ""),
        created_at=_iso_ig(item.get("timestamp")),
        text=item.get("text") or "",
        likes=_int(item.get("likesCount")),
        replies=_int(item.get("repliesCount")),
        depth=1,
        author_hash=anon(oid) if oid else "",
        url=item.get("commentUrl") or "",
    )


def fetch_instagram_details(token, links, on_progress=None):
    if not links:
        return []
    items = run_actor(token, "ig_posts", {
        "directUrls": [l.url for l in links], "resultsType": "posts",
        "resultsLimit": 1, "addParentData": False,
    }, on_progress=on_progress)
    by_code = {}
    for it in items:
        if it.get("error"):
            continue
        code = it.get("shortCode") or _shortcode(it.get("inputUrl") or it.get("url") or "")
        if code and code not in by_code:
            by_code[code] = it
    return [ig_item_to_detail(by_code[l.key], l) if l.key in by_code
            else PostDetail("instagram", l.url, l.key) for l in links]


def fetch_instagram_comments(token, links, per_post: int, on_progress=None):
    if not links or per_post <= 0:
        return []
    items = run_actor(token, "ig_comments", {
        "directUrls": [l.url for l in links], "resultsLimit": int(per_post),
    }, on_progress=on_progress)
    code_to_url = {l.key: l.url for l in links}
    out = []
    for it in items:
        if it.get("error") or not (it.get("text") or it.get("id")):
            continue
        c = ig_item_to_comment(it)
        c.post_url = code_to_url.get(_shortcode(c.post_url), c.post_url)
        out.append(c)
    return out


# ---------------------------------------------------------------- X
def _x_media(item: dict):
    vids = item.get("videoUrls") or []
    imgs = item.get("imageUrls") or []
    murls = item.get("mediaUrls") or []
    if vids:
        kind = "VIDEO"
    elif imgs or murls:
        kind = "IMAGE"
    else:
        kind = "TEXT"
    url = ""
    for cand in (imgs, murls):
        for u in cand or []:
            if isinstance(u, str) and u:
                url = u
                break
        if url:
            break
    return kind, url


def x_item_to_detail(item: dict, link: Link) -> PostDetail:
    kind, murl = _x_media(item)
    aid = str(item.get("authorId") or (item.get("author") or {}).get("id") or "")
    return PostDetail(
        platform="x", url=link.url, key=link.key, found=True,
        created_at=_iso_x(item.get("createdAt")),
        text=item.get("text") or item.get("fullText") or "",
        likes=_int(item.get("likeCount")), comments=_int(item.get("replyCount")),
        shares=_int(item.get("retweetCount")), quotes=_int(item.get("quoteCount")),
        views=_int(item.get("viewCount")),
        media_type=kind, media_url=murl,
        author_hash=anon(aid) if aid else "",
    )


def x_item_to_comment(item: dict) -> Comment:
    aid = str(item.get("authorId") or (item.get("author") or {}).get("id") or "")
    return Comment(
        platform="x",
        post_url=item.get("sourceUrl") or "",
        comment_id=str(item.get("id") or ""),
        created_at=_iso_x(item.get("createdAt")),
        text=item.get("text") or item.get("fullText") or "",
        likes=_int(item.get("likeCount")),
        replies=_int(item.get("replyCount")),
        depth=_int(item.get("depth")) or 1,
        author_hash=anon(aid) if aid else "",
        url=anon_x_url(str(item.get("id") or "")),   # kullanici adi icermeyen link
    )


def fetch_x_details(token, links, on_progress=None):
    if not links:
        return []
    items = run_actor(token, "x_posts", {
        "tweetIds": [l.key for l in links], "maxItems": len(links),
        "outputVariant": "rich", "fieldStyle": "camelCase", "outputPreset": "flat",
    }, on_progress=on_progress)
    wanted = {l.key for l in links}
    by_id = {}
    for it in items:
        iid = str(it.get("id") or "")
        if iid in wanted and iid not in by_id and (it.get("text") or it.get("fullText") or it.get("createdAt")):
            by_id[iid] = it
    return [x_item_to_detail(by_id[l.key], l) if l.key in by_id
            else PostDetail("x", l.url, l.key) for l in links]


def fetch_x_replies(token, links, per_post: int, on_progress=None):
    if not links or per_post <= 0:
        return []
    items = run_actor(token, "x_replies", {
        "startUrls": [l.url for l in links],
        "maxItemsPerTarget": int(per_post), "maxItems": int(per_post) * len(links),
        "scope": "all", "sort": "likes",
        "includeOriginalPost": False, "includeHiddenReplies": False,
        "outputMode": "full", "outputPreset": "flat", "fieldStyle": "camelCase",
    }, on_progress=on_progress)
    id_to_url = {l.key: l.url for l in links}
    out = []
    for it in items:
        kind = str(it.get("resultType") or it.get("type") or "").lower()
        if kind != "reply" or not it.get("id"):
            continue
        c = x_item_to_comment(it)
        src = str(it.get("sourceTweetId") or it.get("rootTweetId") or "")
        c.post_url = id_to_url.get(src, c.post_url)
        out.append(c)
    return out


# ---------------------------------------------------------------- hepsi birden
@dataclass
class LinkReport:
    details: list = field(default_factory=list)
    comments: list = field(default_factory=list)


def estimate(links, per_post: int, with_comments: bool) -> float:
    from connectors.apify_run import estimate_cost
    ig = sum(1 for l in links if l.platform == "instagram")
    xx = len(links) - ig
    cost = estimate_cost("ig_posts", ig) + estimate_cost("x_posts", xx)
    if with_comments:
        cost += estimate_cost("ig_comments", ig * per_post) + estimate_cost("x_replies", xx * per_post)
    return cost


def analyze_links(token, links, with_comments: bool, per_post: int, on_progress=None) -> LinkReport:
    ig = [l for l in links if l.platform == "instagram"]
    xx = [l for l in links if l.platform == "x"]
    details = fetch_instagram_details(token, ig, on_progress) + fetch_x_details(token, xx, on_progress)
    order = {l.url: i for i, l in enumerate(links)}
    details.sort(key=lambda d: order.get(d.url, 0))
    comments = []
    if with_comments:
        comments = (fetch_instagram_comments(token, ig, per_post, on_progress)
                    + fetch_x_replies(token, xx, per_post, on_progress))
    return LinkReport(details=details, comments=comments)
