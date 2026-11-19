import io
from datetime import date
from unittest.mock import patch, MagicMock

from docx import Document

from connectors.base import Post
from export_word import build_links_docx
from merge import merge_posts, posts_from_csv
from sampling import filter_by_date, to_dataframe
from social import Comment, PostDetail, mask_mentions
from timeutil import fmt_tr, to_tr

# ---- Turkiye saati
assert fmt_tr("2026-11-19T15:19:14+00:00") == "2026-11-19 18:19"
assert fmt_tr("2026-11-19T22:30:00Z") == "2026-11-20 01:30"
assert fmt_tr("") == "" and to_tr("bozuk") is None
# gece yarisina yakin UTC gonderi Turkiye'de ertesi gune duser
late = Post("instagram", "1", "2026-10-31T22:00:00+00:00", "", "u", "IMAGE", 0, 0, "")
assert filter_by_date([late], date(2026, 11, 1), date(2026, 11, 1)) == [late]
assert filter_by_date([late], date(2026, 10, 31), date(2026, 10, 31)) == []

# ---- CSV birlestirme (uygulamanin kendi CSV ciktisi -> geri yukleme)
a = Post("instagram", "1", "2026-11-01T10:00:00+00:00", "ilk", "https://www.instagram.com/p/A/", "IMAGE", 5, 1, "h1", "m1")
b = Post("instagram", "2", "2026-11-02T10:00:00+00:00", "ikinci, virgullu \"tirnak\"\nsatir", "https://www.instagram.com/p/B/", "VIDEO", 7, 2, "h2", "")
csv = to_dataframe([a, b]).to_csv(index=False).encode("utf-8-sig")
back = posts_from_csv(csv)
assert [p.post_id for p in back] == ["1", "2"] and back[1].caption == b.caption and back[1].likes == 7
assert back[0].media_url == "m1" and back[1].media_url == ""
a_new = Post("instagram", "1", a.created_at, "ilk", a.permalink, "IMAGE", 50, 9, "h1", "m1")
c = Post("instagram", "3", "2026-11-03T10:00:00+00:00", "ucuncu", "https://www.instagram.com/p/C/", "IMAGE", 1, 0, "h3")
merged = merge_posts(back, [a_new, c])
assert sorted(p.post_id for p in merged) == ["1", "2", "3"]
assert [p.likes for p in merged if p.post_id == "1"] == [50]          # yeni sayilar esas
try:
    posts_from_csv(b"x,y\n1,2\n"); assert False
except ValueError as e:
    assert "eksik sutun" in str(e)
assert merge_posts([], None) == []

# ---- Word link raporu
details = [
    PostDetail("x", "https://x.com/NASA/status/1", "1", True, "2026-11-19T15:19:14+00:00", "Metin @NASA",
               217, 13, 44, 2, 46488, "IMAGE", "https://cdn/a.png", "abc"),
    PostDetail("instagram", "https://www.instagram.com/p/YOK/", "YOK"),
]
comments = [Comment("x", "https://x.com/NASA/status/1", "9", "2026-11-19T15:26:54+00:00", "@NASA harika",
                    1, 0, 1, "def", "https://x.com/i/web/status/9"),
            Comment("x", "https://x.com/NASA/status/1", "10", "2026-11-19T15:30:00+00:00", "yanit\x07",
                    3, 0, 2, "ghi")]
bad = MagicMock(status_code=404, headers={"Content-Type": "text/html"}, content=b"")
with patch("export_word.requests.get", return_value=bad):
    data = build_links_docx(details, comments, {"title": "Deneme", "fetched_at": "2026-11-19 18:30",
                                                 "with_comments": True, "per_post": 20},
                            with_images=True, mask=mask_mentions)
d = Document(io.BytesIO(data))
t = "\n".join(p.text for p in d.paragraphs)
assert "#DATA - HASHTAGdata | Deneme" in t and "1. X gonderisi" in t and "2. Instagram gonderisi" in t
assert "2026-11-19 18:19" in t and "217 begeni" in t and "44 repost" in t and "toplam etkilesim 276" in t
assert "@NASA" not in t and "Metin @kullanici" in t
assert "Yorumlar (2)" in t and "| yanit" in t and "\x07" not in t
assert "bulunamadi" in t and "(Gorsel indirilemedi" in t
rels = [r.target_ref for r in d.part.rels.values() if "hyperlink" in r.reltype]
assert "https://x.com/NASA/status/1" in rels and "https://www.instagram.com/p/YOK/" in rels
assert build_links_docx([], [], {"with_comments": False})
print("merge/time/word OK")
