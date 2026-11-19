"""Uygulamanin uc bolumunu uctan uca test eder (Apify sahte sunucuyla)."""
import os
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from connectors.base import Post
from sampling import to_dataframe
from testutil import FakeApify

APP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "app.py")
P = "connectors.apify_run.requests"


def new():
    return AppTest.from_file(APP, default_timeout=60).run()


def ok(at, where):
    assert not at.exception, (where, at.exception)


def ti(at, label):
    return [t for t in at.text_input if t.label == label][0]


def form_btn(at, label):
    return [b for b in at.button if b.label == label][0]


# acilis
at = new(); ok(at, "acilis")
assert at.title[0].value == "#DATA - HASHTAGdata"
assert len(at.tabs) == 3
print("acilis OK")

# --- Hashtag: demo + liste/tablo + word + csv birlestirme
at = new()
at.selectbox[0].set_value("Demo (sahte veri)")
form_btn(at, "Veriyi cek").click().run(); ok(at, "demo")
vals = [m.value for m in at.metric]
assert vals[:4] == ["30", "30", vals[2], vals[3]] and int(vals[3]) <= 20, vals
[r for r in at.radio if "Tablo" in r.options][0].set_value("Tablo").run(); ok(at, "tablo")
[c for c in at.checkbox if c.label == "Word'e gorselleri de ekle"][0].uncheck().run()
[b for b in at.button if b.label == "Word listesi hazirla"][0].click().run(); ok(at, "word")
assert at.session_state["tag_docx"][:2] == b"PK"
print("hashtag demo OK")

# Apify anahtari olmadan Instagram -> uyari
at = new()
form_btn(at, "Veriyi cek").click().run(); ok(at, "ig anahtarsiz")
assert any("Apify API anahtarini" in e.value for e in at.error)

# Instagram + anahtar + sahte Apify
from datetime import datetime, timezone
now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
ig_items = [{"id": str(i), "shortCode": f"S{i}", "type": "Image", "caption": f"post {i} @biri",
             "url": f"https://www.instagram.com/p/S{i}/", "displayUrl": "https://example.com/i.jpg",
             "likesCount": i, "commentsCount": 1, "timestamp": now, "ownerId": str(100 + i)} for i in range(5)]
fake = FakeApify({"apify~instagram-hashtag-scraper": ig_items})
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    at = new()
    ti(at, "Apify API anahtari").set_value("TOKEN").run()
    form_btn(at, "Veriyi cek").click().run()
ok(at, "ig")
assert [m.value for m in at.metric] == ["5", "5", "5", "5"], [m.value for m in at.metric]
txt = " ".join(t.value for t in at.text)
assert "post 4 @kullanici" in txt and "@biri" not in txt     # @ gizleme
print("hashtag instagram OK")

# X hashtag
x_items = [{"id": "11", "text": "x post #girldate @biri", "createdAt": datetime.now(timezone.utc).strftime("%a %b %d %H:%M:%S +0000 %Y"),
            "likeCount": 3, "replyCount": 1, "authorId": "77"}]
fake = FakeApify({"xquik~x-tweet-scraper": x_items})
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    at = new()
    ti(at, "Apify API anahtari").set_value("TOKEN").run()
    at.selectbox[0].set_value("X / Twitter (Apify, hesapsiz)")
    form_btn(at, "Veriyi cek").click().run()
ok(at, "x")
assert [m.value for m in at.metric][0] == "1", [m.value for m in at.metric]
assert any("i/web/status/11" in m.value for m in at.markdown)
print("hashtag X OK")

# CSV birlestirme: onceki CSV (2 gonderi, biri tekrar) + yeni cekim (5) -> 6
old = [Post("instagram", "1", now.replace(" UTC", "").replace(" ", "T") + "+00:00", "eski", "https://www.instagram.com/p/S1/", "IMAGE", 0, 0, "h"),
       Post("instagram", "OLD", now.replace(" UTC", "").replace(" ", "T") + "+00:00", "eski2", "https://www.instagram.com/p/OLD/", "IMAGE", 0, 0, "h")]
csv_bytes = to_dataframe(old).to_csv(index=False).encode("utf-8-sig")
fake = FakeApify({"apify~instagram-hashtag-scraper": ig_items})

# --- Tek gonderi yorumlari
x_post = {"id": "2123435938848067841", "text": "These baby stars @NASA", "createdAt": "Thu Nov 19 15:19:14 +0000 2026",
          "likeCount": 217, "replyCount": 13, "retweetCount": 44, "quoteCount": 2, "viewCount": 46488, "authorId": "1"}
x_rep = [{"id": str(900 + i), "resultType": "reply", "depth": 1 + (i % 2), "text": f"yanit {i} @biri",
          "createdAt": "Thu Nov 19 15:26:54 +0000 2026", "likeCount": i, "replyCount": 0, "authorId": str(i),
          "sourceTweetId": "2123435938848067841"} for i in range(4)]
fake = FakeApify({"xquik~x-tweet-scraper": [x_post], "xquik~x-reply-scraper": x_rep})
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    at = new()
    ti(at, "Apify API anahtari").set_value("TOKEN").run()
    ti(at, "Gonderi linki").set_value("https://x.com/NASA/status/2123435938848067841?s=20")
    form_btn(at, "Yorumlari cek").click().run()
ok(at, "tek gonderi")
assert at.session_state["one_res"]["details"][0].likes == 217
assert len(at.session_state["one_res"]["comments"]) == 4
assert any("4 yorum (2 dogrudan yorum, 2 yanit)" in c.value for c in at.caption), [c.value for c in at.caption]
assert any("yanit 3 @kullanici" in t.value for t in at.text)
[b for b in at.button if b.label == "Word raporu hazirla"][0].click().run(); ok(at, "tek word")
assert at.session_state["one_docx"][:2] == b"PK"
print("tek gonderi OK")

# gecersiz link
at = new()
ti(at, "Apify API anahtari").set_value("TOKEN").run()
ti(at, "Gonderi linki").set_value("https://example.com/abc")
form_btn(at, "Yorumlari cek").click().run(); ok(at, "gecersiz")
assert any("Gecerli bir Instagram" in e.value for e in at.error)

# --- Toplu link analizi
ig_post = {"id": "4", "shortCode": "Df50n79NQYR", "type": "Video", "caption": "ig metin", "likesCount": 342,
           "commentsCount": 1, "url": "https://www.instagram.com/p/Df50n79NQYR/", "timestamp": "2026-11-19 00:45:26 UTC",
           "ownerId": "9"}
ig_com = {"id": "c1", "text": "ig yorum", "likesCount": 7, "postUrl": "https://www.instagram.com/p/Df50n79NQYR/",
          "timestamp": "2026-11-19 02:24:05 UTC", "owner": {"id": "5"}}
fake = FakeApify({"apify~instagram-scraper": [ig_post], "apify~instagram-comment-scraper": [ig_com],
                  "xquik~x-tweet-scraper": [x_post], "xquik~x-reply-scraper": x_rep})
links_txt = "\n".join(["https://www.instagram.com/p/Df50n79NQYR/", "https://www.instagram.com/p/YOK1/",
                        "https://x.com/NASA/status/2123435938848067841", "bu bir link degil"])
with patch(P + ".post", side_effect=fake.post), patch(P + ".get", side_effect=fake.get):
    at = new()
    ti(at, "Apify API anahtari").set_value("TOKEN").run()
    at.text_area[0].set_value(links_txt)
    form_btn(at, "Linkleri analiz et").click().run()
ok(at, "toplu")
assert any("Taninmayan 1 satir" in w.value for w in at.warning)
vals = [m.value for m in at.metric]
assert "2 / 3" in vals and "559" in vals, vals                    # 342 + 217 begeni
assert len(at.session_state["bulk_res"]["comments"]) == 5
assert at.dataframe, "gonderi tablosu yok"
[b for b in at.button if b.label == "Word raporu hazirla"][0].click().run(); ok(at, "toplu word")
assert at.session_state["bulk_docx"][:2] == b"PK"
print("toplu link OK")

# 100 link siniri
many = "\n".join(f"https://x.com/a/status/{i}" for i in range(101))
at = new()
ti(at, "Apify API anahtari").set_value("TOKEN").run()
at.text_area[0].set_value(many)
form_btn(at, "Linkleri analiz et").click().run(); ok(at, "101")
assert any("En fazla 100" in e.value for e in at.error)
print("TUM UYGULAMA TESTLERI GECTI")
