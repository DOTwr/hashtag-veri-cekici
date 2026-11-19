"""Link ayristirma, gonderi detayi ve yorum testleri (gercek Apify alan adlariyla)."""
from datetime import date
from unittest.mock import patch

from connectors.x_apify import XApifyConnector
from social import (analyze_links, estimate, fetch_x_details, mask_mentions, parse_links)
from testutil import FakeApify

P = "connectors.apify_run.requests"

# ---- link ayristirma
text = """
https://www.instagram.com/p/Df50n79NQYR/
instagram.com/reel/Df68oxghIvQ/?igsh=abc
https://www.instagram.com/kullanici/p/QQQ111/
https://x.com/NASA/status/2123435938848067841?s=20
https://twitter.com/NASA/status/2123435938848067841   (tekrar)
https://mobile.twitter.com/someone/status/42
merhaba, https://example.com/x
"""
links, bad = parse_links(text)
assert [(l.platform, l.key) for l in links] == [
    ("instagram", "Df50n79NQYR"), ("instagram", "Df68oxghIvQ"), ("instagram", "QQQ111"),
    ("x", "2123435938848067841"), ("x", "42")], links
assert links[1].url == "https://www.instagram.com/reel/Df68oxghIvQ/"
assert links[3].url == "https://x.com/NASA/status/2123435938848067841"
assert bad == ["merhaba, https://example.com/x"], bad
# ayni satirda birden fazla link
l2, b2 = parse_links("a https://x.com/u/status/1, https://www.instagram.com/p/Z/ b")
assert [l.key for l in l2] == ["1", "Z"] and b2 == []
assert parse_links("")[0] == [] and parse_links(None)[0] == []
assert mask_mentions("@NASA @chandra.xray harika e@mail") == "@kullanici @kullanici harika e@kullanici"

# ---- gercek ciktilardan alinmis ornekler
ig_post = {"id": "4033486384142812689", "shortCode": "Df50n79NQYR", "type": "Video",
           "caption": "guess which one has a bf", "likesCount": 342, "commentsCount": 1,
           "url": "https://www.instagram.com/p/Df50n79NQYR/", "inputUrl": "https://www.instagram.com/p/Df50n79NQYR/",
           "timestamp": "2026-11-19 00:45:26 UTC", "displayUrl": "https://cdn/ig1.jpg",
           "videoPlayCount": 24992, "ownerId": "76272118937", "ownerUsername": "notnormalave"}
ig_comment = {"id": "18099712658405522", "text": "The tribal gongs @someone", "likesCount": 7,
              "ownerUsername": "adda_roll", "owner": {"id": "555"}, "postUrl": "https://www.instagram.com/p/Df50n79NQYR/",
              "commentUrl": "https://www.instagram.com/p/Df50n79NQYR/c/18099712658405522",
              "repliesCount": None, "timestamp": "2026-11-19 02:24:05 UTC"}
x_post = {"id": "2123435938848067841", "type": "tweet", "text": "These baby stars",
          "createdAt": "Thu Nov 19 15:19:14 +0000 2026", "likeCount": 217, "replyCount": 13,
          "retweetCount": 44, "quoteCount": 2, "viewCount": 46488, "authorId": "11348282",
          "authorUsername": "NASA", "url": "https://x.com/NASA/status/2123435938848067841",
          "mediaUrls": ["https://pbs.twimg.com/media/a.jpg"], "videoUrls": []}
x_reply = {"id": "2123437870404829418", "type": "reply", "resultType": "reply", "depth": 1,
           "text": "@NASA @chandraxray Finally a newborn", "createdAt": "Thu Nov 19 15:26:54 +0000 2026",
           "likeCount": 1, "replyCount": 0, "authorId": "1328206255681384448", "authorUsername": "Neutral314",
           "sourceTweetId": "2123435938848067841", "sourceUrl": "https://x.com/NASA/status/2123435938848067841",
           "url": "https://x.com/Neutral314/status/2123437870404829418"}
x_nested = dict(x_reply, id="777", depth=2, likeCount=5, text="yanita yanit")
x_status_row = {"type": "runStatus", "resultType": "status", "message": "ok"}

fake = FakeApify({
    "apify~instagram-scraper": [ig_post, {"error": "not_found", "inputUrl": "https://www.instagram.com/p/YOK123/"}],
    "apify~instagram-comment-scraper": [ig_comment],
    "xquik~x-tweet-scraper": [x_post, {"type": "inputStatus", "id": None}],
    "xquik~x-reply-scraper": [x_reply, x_nested, x_status_row],
})
links, _ = parse_links("https://www.instagram.com/p/Df50n79NQYR/ https://www.instagram.com/p/YOK123/ "
                       "https://x.com/NASA/status/2123435938848067841")
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    rep = analyze_links("TOK", links, with_comments=True, per_post=10)

# girdiler
inputs = {a: j for a, j, _ in fake.calls}
assert inputs["apify~instagram-scraper"]["directUrls"] == ["https://www.instagram.com/p/Df50n79NQYR/",
                                                            "https://www.instagram.com/p/YOK123/"]
assert inputs["apify~instagram-scraper"]["resultsLimit"] == 1
assert inputs["apify~instagram-comment-scraper"] == {"directUrls": inputs["apify~instagram-scraper"]["directUrls"],
                                                      "resultsLimit": 10}
assert inputs["xquik~x-tweet-scraper"]["tweetIds"] == ["2123435938848067841"]
assert inputs["xquik~x-reply-scraper"]["startUrls"] == ["https://x.com/NASA/status/2123435938848067841"]
assert inputs["xquik~x-reply-scraper"]["maxItemsPerTarget"] == 10

# detaylar: sira korunur, bulunamayan isaretlenir
assert [d.url for d in rep.details] == [l.url for l in links]
ig, missing, xx = rep.details
assert ig.found and ig.likes == 342 and ig.comments == 1 and ig.views == 24992 and ig.media_type == "VIDEO"
assert ig.created_at == "2026-11-19T00:45:26+00:00" and ig.media_url == "https://cdn/ig1.jpg"
assert ig.engagement == 343 and "76272118937" not in ig.author_hash
assert not missing.found
assert xx.found and (xx.likes, xx.comments, xx.shares, xx.quotes, xx.views) == (217, 13, 44, 2, 46488)
assert xx.created_at == "2026-11-19T15:19:14+00:00" and xx.engagement == 276
assert xx.media_type == "IMAGE" and xx.media_url == "https://pbs.twimg.com/media/a.jpg"

# yorumlar
assert len(rep.comments) == 3
c_ig = [c for c in rep.comments if c.platform == "instagram"][0]
assert c_ig.post_url == ig.url and c_ig.likes == 7 and c_ig.replies == 0 and c_ig.depth == 1
assert c_ig.created_at == "2026-11-19T02:24:05+00:00" and "555" not in c_ig.author_hash
x_cs = [c for c in rep.comments if c.platform == "x"]
assert [c.depth for c in x_cs] == [1, 2] and all(c.post_url == xx.url for c in x_cs)
assert x_cs[0].url == "https://x.com/i/web/status/2123437870404829418"   # kullanici adi yok
assert "Neutral314" not in x_cs[0].url

# yorumsuz calisma: yorum araclari cagrilmaz
fake2 = FakeApify({"apify~instagram-scraper": [ig_post]})
with patch(P + ".post", side_effect=fake2.post), patch(P + ".get", side_effect=fake2.get):
    rep2 = analyze_links("TOK", links[:1], with_comments=False, per_post=10)
assert [a for a, _, _ in fake2.calls] == ["apify~instagram-scraper"] and rep2.comments == []

# bos liste: hicbir arac cagrilmaz
fake3 = FakeApify({})
with patch(P + ".post", side_effect=fake3.post), patch(P + ".get", side_effect=fake3.get):
    assert fetch_x_details("TOK", []) == [] and fake3.calls == []

# maliyet tahmini
assert round(estimate(links, 10, True), 4) == round((2*2.70 + 0.15 + 2*10*2.60 + 10*0.15) / 1000, 4)

# ---- X hashtag arama
fake4 = FakeApify({"xquik~x-tweet-scraper": [x_post, x_post, x_status_row]})
with patch(P + ".post", side_effect=fake4.post), patch(P + ".get", side_effect=fake4.get):
    posts = XApifyConnector("TOK").fetch("#girldate", date(2026, 11, 1), date(2026, 11, 19), 30)
body = fake4.calls[0][1]
assert body["searchTerms"] == ["#girldate"] and body["since"] == "2026-11-01" and body["until"] == "2026-11-20"
assert body["maxItems"] == 30 and body["queryType"] == "Latest"
assert len(posts) == 1
p = posts[0]
assert p.platform == "x" and p.permalink == "https://x.com/i/web/status/2123435938848067841"
assert p.likes == 217 and p.comments == 13 and p.media_type == "IMAGE" and "11348282" not in p.author_hash
print("social OK")
