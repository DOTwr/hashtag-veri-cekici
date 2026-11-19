"""Onceki cekimleri (bu uygulamadan indirilmis CSV'ler) yeni cekimle birlestirme.

Ucretsiz planda her aramada ~30 gonderi geldigi icin, farkli gunlerde yapilan
cekimler birlestirilerek havuz buyutulur. Ayni gonderi iki kez sayilmaz.
"""
import io

import pandas as pd

from connectors.base import Post

REQUIRED = ["post_id", "permalink"]


def _int(v) -> int:
    try:
        return max(int(float(v)), 0)
    except (TypeError, ValueError):
        return 0


def _str(v) -> str:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    return str(v)


def posts_from_csv(data: bytes) -> list:
    """Uygulamanin 'CSV indir' ciktisini Post listesine cevirir."""
    df = None
    for enc in ("utf-8-sig", "utf-8", "cp1254", "latin-1"):
        try:
            df = pd.read_csv(io.BytesIO(data), encoding=enc, dtype=str)
            break
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    if df is None:
        raise ValueError("CSV dosyasi okunamadi.")
    missing = [c for c in REQUIRED if c not in df.columns]
    if missing:
        raise ValueError("Bu CSV bu uygulamanin hashtag ciktisi degil (eksik sutun: " + ", ".join(missing) + ").")
    out = []
    for _, r in df.iterrows():
        pid, link = _str(r.get("post_id")), _str(r.get("permalink"))
        if not pid and not link:
            continue
        out.append(Post(
            platform=_str(r.get("platform")) or "instagram",
            post_id=pid or link,
            created_at=_str(r.get("created_at")),
            caption=_str(r.get("caption")),
            permalink=link,
            media_type=_str(r.get("media_type")),
            likes=_int(r.get("likes")),
            comments=_int(r.get("comments")),
            author_hash=_str(r.get("author_hash")),
            media_url=_str(r.get("media_url")),
        ))
    return out


def merge_posts(*groups) -> list:
    """Gruplari birlestirir; ayni gonderi (platform + id) bir kez tutulur.
    Sonra gelen gruptaki (daha yeni) begeni/yorum sayilari esas alinir."""
    merged = {}
    for group in groups:
        for p in group or []:
            key = (p.platform, p.post_id)
            merged[key] = p
    return list(merged.values())
