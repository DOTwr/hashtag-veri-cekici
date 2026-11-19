import sqlite3
from datetime import date, datetime, timezone

from connectors.base import Connector, Post

DB_PATH = "arsiv.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS posts (
    platform TEXT NOT NULL,
    post_id TEXT NOT NULL,
    hashtag TEXT NOT NULL,
    created_at TEXT,
    caption TEXT,
    permalink TEXT,
    media_type TEXT,
    likes INTEGER,
    comments INTEGER,
    author_hash TEXT,
    first_seen TEXT,
    last_seen TEXT,
    PRIMARY KEY (platform, post_id, hashtag)
)
"""


class Archive:
    def __init__(self, path: str = DB_PATH):
        self.path = path
        with self._conn() as c:
            c.execute(SCHEMA)

    def _conn(self):
        return sqlite3.connect(self.path)

    def save(self, posts, hashtag: str) -> int:
        """Yeni gonderileri ekler, var olanlarin begeni/yorum sayisini gunceller."""
        tag = hashtag.lstrip("#").strip().lower()
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        with self._conn() as c:
            for p in posts:
                c.execute(
                    """INSERT INTO posts (platform, post_id, hashtag, created_at, caption,
                           permalink, media_type, likes, comments, author_hash, first_seen, last_seen)
                       VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
                       ON CONFLICT(platform, post_id, hashtag) DO UPDATE SET
                           likes=excluded.likes, comments=excluded.comments,
                           last_seen=excluded.last_seen""",
                    (p.platform, p.post_id, tag, p.created_at, p.caption, p.permalink,
                     p.media_type, p.likes, p.comments, p.author_hash, now, now),
                )
        return len(posts)

    def load(self, hashtag: str, platform: str = "instagram", limit: int = 100000):
        tag = hashtag.lstrip("#").strip().lower()
        with self._conn() as c:
            rows = c.execute(
                """SELECT platform, post_id, created_at, caption, permalink, media_type,
                          likes, comments, author_hash
                   FROM posts WHERE hashtag=? AND platform=? ORDER BY created_at DESC LIMIT ?""",
                (tag, platform, limit),
            ).fetchall()
        return [Post(*r) for r in rows]

    def summary(self):
        """(platform, hashtag, gonderi sayisi, en eski, en yeni) listesi."""
        with self._conn() as c:
            return c.execute(
                """SELECT platform, hashtag, COUNT(*), MIN(created_at), MAX(created_at)
                   FROM posts GROUP BY platform, hashtag ORDER BY platform, hashtag"""
            ).fetchall()


class ArchiveConnector(Connector):
    name = "Kendi arsivimiz (SQLite)"
    notes = ["Veri, daha once kaydedilen gunluk cekimlerden gelir; arsivin basladigi tarihten oncesi yoktur."]

    def __init__(self, platform: str = "instagram", path: str = DB_PATH):
        self.platform = platform
        self.archive = Archive(path)

    def fetch(self, hashtag, start: date, end: date, pool_limit: int):
        return self.archive.load(hashtag, self.platform, int(pool_limit))
