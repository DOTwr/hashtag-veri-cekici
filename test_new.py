import os, tempfile
from datetime import date
from unittest.mock import patch, MagicMock

from archive import Archive, ArchiveConnector
from connectors.bluesky import BlueskyConnector
from connectors.mock import MockConnector
from sampling import filter_by_date

# --- Arsiv ---
db = os.path.join(tempfile.mkdtemp(), "t.db")
pool = MockConnector().fetch("GirlDate", date(2026, 10, 1), date(2026, 10, 31), 100)
a = Archive(db)
a.save(pool, "#GirlDate")
a.save(pool, "girldate")                       # tekrar: cogalmamali
assert len(a.load("girldate", "instagram")) == 100
pool[0].likes = 99999
a.save(pool, "girldate")                       # guncelleme
assert max(p.likes for p in a.load("girldate")) == 99999
assert len(a.load("girldate")) == 100
assert a.load("baska") == []
s = a.summary()
assert s[0][0:3] == ("instagram", "girldate", 100)
ac = ArchiveConnector("instagram", db).fetch("girldate", date(2026,10,1), date(2026,10,31), 500)
assert len(filter_by_date(ac, date(2026,10,1), date(2026,10,31))) > 0
print("arsiv OK")

# --- Bluesky (sahte HTTP) ---
def resp(code, js):
    m = MagicMock(); m.status_code = code; m.json.return_value = js; m.text = str(js); return m

def post(i):
    return {"uri": f"at://did:plc:x{i}/app.bsky.feed.post/rk{i}",
            "author": {"did": f"did:plc:x{i}", "handle": f"u{i}.bsky.social"},
            "record": {"text": f"merhaba #girldate {i}", "createdAt": "2026-10-05T10:00:00.000Z"},
            "likeCount": i, "replyCount": 1, "indexedAt": "2026-10-05T10:00:01Z",
            "embed": {"$type": "app.bsky.embed.images#view"}}

calls = []
def fake_get(url, params=None, headers=None, timeout=0):
    calls.append(dict(params))
    if "cursor" not in params:
        return resp(200, {"posts": [post(1), post(2)], "cursor": "c1"})
    return resp(200, {"posts": [post(3)]})

with patch("connectors.bluesky.requests.post", return_value=resp(200, {"accessJwt": "T"})), \
     patch("connectors.bluesky.requests.get", side_effect=fake_get):
    out = BlueskyConnector("@ben.bsky.social", "pw").fetch("#girldate", date(2026,10,1), date(2026,10,31), 100)

assert len(out) == 3 and calls[0]["tag"] == "girldate"
assert calls[0]["since"] == "2026-10-01T00:00:00Z" and calls[0]["until"] == "2026-11-01T00:00:00Z"
assert out[0].permalink == "https://bsky.app/profile/u1.bsky.social/post/rk1"
assert out[0].media_type == "IMAGE" and out[0].platform == "bluesky"
assert BlueskyConnector._media_url({"embed": {"images": [{"thumb": "https://t/1.jpg"}]}}) == "https://t/1.jpg"
assert BlueskyConnector._media_url({}) == ""
assert len(filter_by_date(out, date(2026,10,1), date(2026,10,31))) == 3
assert all("did:plc" not in p.author_hash for p in out)

with patch("connectors.bluesky.requests.post", return_value=resp(401, {})):
    try: BlueskyConnector("a", "b").fetch("x", date(2026,1,1), date(2026,1,2), 10); assert False
    except RuntimeError as e: assert "girisi" in str(e)

with patch("connectors.bluesky.requests.post", return_value=resp(200, {"accessJwt": "T"})), \
     patch("connectors.bluesky.requests.get", return_value=resp(429, {})):
    try: BlueskyConnector("a", "b").fetch("x", date(2026,1,1), date(2026,1,2), 10); assert False
    except RuntimeError as e: assert "limit" in str(e)

with patch("connectors.bluesky.requests.post", return_value=resp(200, {"accessJwt": "T"})), \
     patch("connectors.bluesky.requests.get", side_effect=fake_get):
    assert len(BlueskyConnector("a","b").fetch("x", date(2026,10,1), date(2026,10,31), 2)) == 2
print("bluesky OK")
