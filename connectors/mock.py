import hashlib
import random
import zlib
from datetime import date, datetime, timedelta, timezone

from .base import Connector, Post

_WORDS = ["bugun", "aksam", "kahve", "film", "yuruyus", "sahil", "restoran",
          "ilk", "bulusma", "mutlu", "plan", "muzik", "tatli", "sehir"]


class MockConnector(Connector):
    name = "Demo (sahte veri)"
    notes = ["Bu veriler uydurmadir; sadece arayuzu ve mantigi denemek icin."]

    def fetch(self, hashtag, start, end, pool_limit):
        rng = random.Random(zlib.crc32(hashtag.encode("utf-8")))
        days = max((end - start).days, 1)
        posts = []
        for i in range(pool_limit):
            d = datetime.combine(start, datetime.min.time(), tzinfo=timezone.utc) \
                + timedelta(days=rng.random() * days, seconds=rng.randint(0, 86399))
            cap = " ".join(rng.choices(_WORDS, k=rng.randint(4, 10))) + f" #{hashtag}"
            user = f"kullanici_{rng.randint(1, 400)}"
            posts.append(Post(
                platform="instagram",
                post_id=f"demo_{i}",
                created_at=d.isoformat(),
                caption=cap,
                permalink=f"https://www.instagram.com/p/DEMO{i:05d}/",
                media_type=rng.choice(["IMAGE", "VIDEO", "CAROUSEL_ALBUM"]),
                likes=int(rng.paretovariate(1.2) * 10),
                comments=int(rng.paretovariate(1.5) * 2),
                author_hash=hashlib.sha256(user.encode()).hexdigest()[:10],
            ))
        return posts
