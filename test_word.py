import io, struct, zlib
from unittest.mock import patch, MagicMock
from docx import Document
from connectors.base import Post
from export_word import build_docx

def png():
    raw = b"\x00\xff\x00\x00"
    def chunk(t, d): return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xffffffff)
    return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
            + chunk(b"IDAT", zlib.compress(raw)) + chunk(b"IEND", b""))

posts = [
    Post("instagram", "1", "2026-11-19T13:21:39+00:00", "Kafe sonrasi ❤️ #girldate\nikinci satir\x07",
         "https://www.instagram.com/p/AAA/", "VIDEO", 5, 0, "abc", "https://cdn/x.png"),
    Post("instagram", "2", "2026-11-13T23:25:50+00:00", "", "https://www.instagram.com/p/BBB/",
         "CAROUSEL_ALBUM", 372, 4, "def", "https://cdn/y.png"),
    Post("instagram", "3", "", "metin", "", "IMAGE", 0, 0, "", ""),
]
meta = {"hashtag": "girldate", "conn_name": "Instagram (Apify, hesapsiz)", "start": "2026-11-01",
        "end": "2026-11-30", "mode": "En yeni", "seed": 42, "fetched_at": "2026-11-19T17:52:00"}

ok = MagicMock(status_code=200, headers={"Content-Type": "image/png"}, content=png())
bad = MagicMock(status_code=403, headers={"Content-Type": "text/html"}, content=b"no")
with patch("export_word.requests.get", side_effect=[ok, bad]):
    data = build_docx(posts, meta, with_images=True)
d = Document(io.BytesIO(data))
text = "\n".join(p.text for p in d.paragraphs)
assert "#girldate gonderi listesi" in text and "3. gonderi" in text
assert "Kafe sonrasi" in text and "\x07" not in text
assert "(aciklama yok)" in text and "(Gorsel indirilemedi" in text
assert len(d.inline_shapes) == 1
rels = [r.target_ref for r in d.part.rels.values() if "hyperlink" in r.reltype]
assert rels == ["https://www.instagram.com/p/AAA/", "https://www.instagram.com/p/BBB/"], rels

with patch("export_word.requests.get") as g:
    data2 = build_docx(posts, meta, with_images=False); assert not g.called
assert len(Document(io.BytesIO(data2)).inline_shapes) == 0
assert build_docx([], meta)  # bos liste de calisir
print("word OK")
