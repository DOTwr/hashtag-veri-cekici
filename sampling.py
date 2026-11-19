import random
from datetime import date, datetime, timezone

import pandas as pd

MODES = {
    "En populer (begeni + yorum)": "popular",
    "Rastgele (havuzdan, seed'li)": "random",
    "En yeni": "newest",
}


def _to_date(iso: str):
    try:
        return datetime.fromisoformat(iso).astimezone(timezone.utc).date()
    except ValueError:
        return None


def filter_by_date(posts, start: date, end: date):
    out = []
    for p in posts:
        d = _to_date(p.created_at)
        if d is not None and start <= d <= end:
            out.append(p)
    return out


def select(posts, mode: str, n: int, seed: int = 42):
    if mode == "popular":
        return sorted(posts, key=lambda p: p.likes + p.comments, reverse=True)[:n]
    if mode == "newest":
        return sorted(posts, key=lambda p: p.created_at, reverse=True)[:n]
    if mode == "random":
        rng = random.Random(seed)
        return rng.sample(posts, min(n, len(posts)))
    raise ValueError(f"Bilinmeyen mod: {mode}")


def to_dataframe(posts) -> pd.DataFrame:
    cols = ["created_at", "author_hash", "caption", "media_type", "media_url",
            "likes", "comments", "permalink", "post_id", "platform"]
    if not posts:
        return pd.DataFrame(columns=cols)
    return pd.DataFrame([vars(p) for p in posts])[cols]
