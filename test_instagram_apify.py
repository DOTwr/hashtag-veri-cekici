from datetime import date
from unittest.mock import patch, MagicMock
import requests as _rq

from connectors.instagram_apify import InstagramApifyConnector, item_to_post
from sampling import filter_by_date

def resp(code, js):
    m = MagicMock(); m.status_code = code; m.json.return_value = js; m.text = str(js); return m

items = [
    {"id": "1", "type": "Image", "shortCode": "AAA", "caption": "ilk bulusma #girldate",
     "url": "https://www.instagram.com/p/AAA/", "displayUrl": "https://cdn/1.jpg",
     "likesCount": 120, "commentsCount": 4, "timestamp": "2026-11-10T12:00:00.000Z",
     "ownerUsername": "ayse", "ownerId": "999"},
    {"id": "2", "type": "Video", "shortCode": "BBB", "caption": "aksam",
     "displayUrl": "https://cdn/2.jpg", "videoUrl": "https://cdn/2.mp4",
     "likesCount": -1, "commentsCount": None, "timestamp": "2026-10-01T08:00:00.000Z",
     "ownerUsername": "fatma"},
    {"id": "1", "type": "Image", "url": "https://www.instagram.com/p/AAA/"},   # tekrar
    {"error": "no_items"},                                                         # hata kaydi
    "bozuk",
]

sent = {}
def fake_post(url, params=None, headers=None, json=None, timeout=0):
    sent.update(url=url, params=params, headers=headers, json=json); return resp(201, items)

with patch("connectors.instagram_apify.requests.post", side_effect=fake_post):
    out = InstagramApifyConnector(" TOKEN ").fetch("#girldate", date(2026,11,1), date(2026,11,30), 50)

assert sent["json"] == {"hashtags": ["girldate"], "resultsType": "posts", "resultsLimit": 50}
assert sent["headers"]["Authorization"] == "Bearer TOKEN" and "token" not in (sent["params"] or {})
assert "apify~instagram-hashtag-scraper/run-sync-get-dataset-items" in sent["url"]
assert len(out) == 2
a, b = out
assert a.caption == "ilk bulusma #girldate" and a.permalink == "https://www.instagram.com/p/AAA/"
assert a.media_url == "https://cdn/1.jpg" and a.media_type == "IMAGE" and a.likes == 120
assert "ayse" not in a.author_hash and "999" not in a.author_hash and len(a.author_hash) == 10
assert b.permalink == "https://www.instagram.com/p/BBB/" and b.media_type == "VIDEO"
assert b.likes == 0 and b.comments == 0
assert [p.post_id for p in filter_by_date(out, date(2026,11,1), date(2026,11,30))] == ["1"]

# limit
with patch("connectors.instagram_apify.requests.post", side_effect=fake_post):
    assert len(InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,12,31), 1)) == 1
# bos sonuc
with patch("connectors.instagram_apify.requests.post", return_value=resp(201, [])):
    assert InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5) == []
# hatalar
for code, word in [(401, "gecersiz"), (402, "kredisi"), (408, "zamaninda"), (500, "hatasi")]:
    with patch("connectors.instagram_apify.requests.post", return_value=resp(code, {})):
        try: InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
        except RuntimeError as e: assert word in str(e), e
with patch("connectors.instagram_apify.requests.post", return_value=resp(200, {"error": "x"})):
    try: InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
    except RuntimeError as e: assert "beklenmeyen" in str(e)
for exc, word in [(_rq.Timeout(), "zaman asimi"), (_rq.ConnectionError(), "baglanilamadi")]:
    with patch("connectors.instagram_apify.requests.post", side_effect=exc):
        try: InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
        except RuntimeError as e: assert word in str(e), e
try: InstagramApifyConnector("").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
except RuntimeError as e: assert "anahtari" in str(e)
# eksik alanli kayit
p = item_to_post({"shortCode": "CCC"})
assert p.permalink == "https://www.instagram.com/p/CCC/" and p.media_type == "TEXT" and p.created_at == ""
print("instagram apify OK")
