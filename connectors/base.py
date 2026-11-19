from dataclasses import dataclass
from datetime import date


@dataclass
class Post:
    platform: str
    post_id: str
    created_at: str      # ISO format
    caption: str
    permalink: str
    media_type: str
    likes: int
    comments: int
    author_hash: str     # anonim; gercek kullanici adi tutulmaz
    media_url: str = ""  # gorsel/video onizleme linki (varsa)


class Connector:
    name = "base"
    # Kaynagin kendi siralamasi algoritmik mi? (arayuzde uyari icin)
    notes: list = []

    def fetch(self, hashtag: str, start: date, end: date, pool_limit: int) -> list:
        raise NotImplementedError


def anon(value: str) -> str:
    """Kullanici kimligini tuzlu hash ile anonimlestirir (geri donusturulemez).
    Tuzu ANON_SALT ortam degiskeniyle kendi gizli degerinle degistir."""
    import hashlib
    import os
    salt = os.environ.get("ANON_SALT", "degistir-beni")
    return hashlib.sha256((salt + value).encode("utf-8")).hexdigest()[:10]
