from datetime import date
from unittest.mock import patch
import requests as _rq

from connectors.instagram_apify import InstagramApifyConnector, item_to_post
from sampling import filter_by_date
from testutil import FakeApify, resp

items = [
    {"id": "1", "type": "Image", "shortCode": "AAA", "caption": "ilk bulusma #girldate",
     "url": "https://www.instagram.com/p/AAA/", "displayUrl": "https://cdn/1.jpg",
     "likesCount": 120, "commentsCount": 4, "timestamp": "2026-11-10T12:00:00.000Z",
     "ownerUsername": "ayse", "ownerId": "999"},
    {"id": "2", "type": "Video", "shortCode": "BBB", "caption": "aksam",
     "displayUrl": "https://cdn/2.jpg", "videoUrl": "https://cdn/2.mp4",
     "likesCount": -1, "commentsCount": None, "timestamp": "2026-10-01 08:00:00 UTC",   # gercek bicim
     "ownerUsername": "fatma"},
    {"id": "1", "type": "Image", "url": "https://www.instagram.com/p/AAA/"},   # tekrar
    {"error": "no_items"},
    "bozuk",
]
P = "connectors.apify_run.requests"

fake = FakeApify({"apify~instagram-hashtag-scraper": items})
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    out = InstagramApifyConnector(" TOKEN ").fetch("#girldate", date(2026,11,1), date(2026,11,30), 50)

actor, body, headers = fake.calls[0]
assert actor == "apify~instagram-hashtag-scraper"
assert body == {"hashtags": ["girldate"], "resultsType": "posts", "resultsLimit": 50}
assert headers["Authorization"] == "Bearer TOKEN"
assert len(out) == 2
a, b = out
assert a.caption == "ilk bulusma #girldate" and a.permalink == "https://www.instagram.com/p/AAA/"
assert a.media_url == "https://cdn/1.jpg" and a.media_type == "IMAGE" and a.likes == 120
assert "ayse" not in a.author_hash and "999" not in a.author_hash and len(a.author_hash) == 10
assert b.permalink == "https://www.instagram.com/p/BBB/" and b.media_type == "VIDEO"
assert b.likes == 0 and b.comments == 0
assert b.created_at == "2026-10-01T08:00:00+00:00", b.created_at
assert [p.post_id for p in filter_by_date(out, date(2026,11,1), date(2026,11,30))] == ["1"]

# limit
fake = FakeApify({"apify~instagram-hashtag-scraper": items})
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    assert len(InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,12,31), 1)) == 1

# gecmis calistirmalar: ayni hashtag eklenir, farkli hashtag eklenmez, tekrar sayilmaz
fake = FakeApify({"apify~instagram-hashtag-scraper": items[:1]},
                 runs=[{"status": "SUCCEEDED", "defaultKeyValueStoreId": "k1", "defaultDatasetId": "old1"},
                       {"status": "SUCCEEDED", "defaultKeyValueStoreId": "k2", "defaultDatasetId": "old2"},
                       {"status": "SUCCEEDED", "defaultKeyValueStoreId": "k3", "defaultDatasetId": "old3"}],
                 inputs={"k1": {"hashtags": ["#GirlDate"]}, "k2": {"hashtags": ["baska"]}})
fake.items["old1"] = [items[0], items[1]]
fake.items["old2"] = [{"id": "9", "shortCode": "ZZZ", "url": "https://www.instagram.com/p/ZZZ/"}]
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    out = InstagramApifyConnector("T", include_history=True).fetch("girldate", date(2026,1,1), date(2026,12,31), 30)
assert sorted(p.post_id for p in out) == ["1", "2"], [p.post_id for p in out]

# hatalar
for code, word in [(401, "gecersiz"), (402, "kredisi"), (403, "reddetti"), (500, "hatasi")]:
    fake = FakeApify({}, start_code=code)
    with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
        try: InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
        except RuntimeError as e: assert word in str(e), e
fake = FakeApify({}, final_status="FAILED")
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    try: InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
    except RuntimeError as e: assert "basarisiz" in str(e)
for exc, word in [(_rq.Timeout(), "zaman asimi"), (_rq.ConnectionError(), "baglanilamadi")]:
    with patch(P + ".post", side_effect=exc):
        try: InstagramApifyConnector("T").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
        except RuntimeError as e: assert word in str(e), e
try: InstagramApifyConnector("").fetch("x", date(2026,1,1), date(2026,1,2), 5); assert False
except RuntimeError as e: assert "anahtari" in str(e)
p = item_to_post({"shortCode": "CCC"})
assert p.permalink == "https://www.instagram.com/p/CCC/" and p.media_type == "TEXT" and p.created_at == ""
print("instagram apify OK")
