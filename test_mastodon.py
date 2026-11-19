from datetime import date
from unittest.mock import patch, MagicMock
from connectors.mastodon import MastodonConnector, _clean
from sampling import filter_by_date

def resp(code, js):
    m = MagicMock(); m.status_code = code; m.json.return_value = js; m.text = str(js); return m

def st(i, day):
    return {"id": str(1000 + i), "created_at": f"2026-10-{day:02d}T10:00:00.000Z",
            "url": f"https://mastodon.social/@u{i}/{1000+i}",
            "content": f"<p>merhaba &amp; <a href='#'>#girldate</a> {i}<br>iki</p>",
            "favourites_count": i, "replies_count": 1,
            "account": {"id": str(i), "acct": f"u{i}"},
            "media_attachments": [{"type": "image"}]}

assert _clean("<p>a &amp; b<br/>c</p>") == "a & b\nc"

pages = [
    [st(5, 20), st(4, 15)],        # sayfa 1 (id azalan)
    [st(3, 10), st(2, 3)],         # sayfa 2: 3 Ekim -> baslangictan (5 Ekim) once
    [st(1, 1)],                    # cagirilmamali
]
calls = []
def fake_get(url, params=None, timeout=0):
    calls.append(dict(params)); return resp(200, pages[len(calls) - 1])

with patch("connectors.mastodon.requests.get", side_effect=fake_get), patch("connectors.mastodon.time.sleep"):
    out = MastodonConnector("https://Mastodon.Social/").fetch("#girldate", date(2026,10,5), date(2026,10,31), 100)

assert calls[0] == {"limit": 40} and calls[1]["max_id"] == "1004", calls
assert len(calls) == 2                               # baslangictan once ulasinca durdu
assert [p.post_id for p in out] == ["mastodon.social:1005", "mastodon.social:1004", "mastodon.social:1003"]
assert out[0].caption == "merhaba & #girldate 5\niki" and out[0].media_type == "IMAGE"
assert out[0].platform == "mastodon" and "account" not in out[0].author_hash
assert len(filter_by_date(out, date(2026,10,5), date(2026,10,31))) == 3

# pool_limit
with patch("connectors.mastodon.requests.get", side_effect=lambda u, params=None, timeout=0: resp(200, pages[0])), patch("connectors.mastodon.time.sleep"):
    assert len(MastodonConnector().fetch("x", date(2026,10,1), date(2026,10,31), 1)) == 1
# bos sonuc
with patch("connectors.mastodon.requests.get", return_value=resp(200, [])):
    assert MastodonConnector().fetch("x", date(2026,10,1), date(2026,10,31), 10) == []
# hatalar
for code, word in [(401, "kapatmis"), (429, "limiti"), (500, "hatasi")]:
    with patch("connectors.mastodon.requests.get", return_value=resp(code, {})):
        try: MastodonConnector().fetch("x", date(2026,10,1), date(2026,10,2), 10); assert False
        except RuntimeError as e: assert word in str(e), e
print("mastodon OK")

import requests as _rq
with patch("connectors.mastodon.requests.get", side_effect=_rq.ConnectionError("x")):
    try: MastodonConnector().fetch("x", date(2026,10,1), date(2026,10,2), 10); assert False
    except RuntimeError as e: assert "baglanilamadi" in str(e), e
print("mastodon baglanti hatasi OK")

from connectors.mastodon import _media_url
assert _media_url([{"type": "image", "preview_url": "https://x/p.jpg", "url": "https://x/f.jpg"}]) == "https://x/p.jpg"
assert _media_url([]) == "" and _media_url(None) == ""
print("medya onizleme OK")
