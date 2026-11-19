"""Secilen gonderileri Word (.docx) listesi olarak disa aktarir."""
import io

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor

from timeutil import fmt_tr


def _add_link(paragraph, url: str, text: str):
    """Paragrafa tiklanabilir kopru ekler."""
    r_id = paragraph.part.relate_to(url, RELATIONSHIP_TYPE.HYPERLINK, is_external=True)
    link = OxmlElement("w:hyperlink")
    link.set(qn("r:id"), r_id)
    run = OxmlElement("w:r")
    rpr = OxmlElement("w:rPr")
    color = OxmlElement("w:color")
    color.set(qn("w:val"), "0563C1")
    underline = OxmlElement("w:u")
    underline.set(qn("w:val"), "single")
    rpr.append(color)
    rpr.append(underline)
    run.append(rpr)
    t = OxmlElement("w:t")
    t.text = text
    t.set(qn("xml:space"), "preserve")
    run.append(t)
    link.append(run)
    paragraph._p.append(link)


def _download_image(url: str, timeout: int = 10):
    """Gorseli indirir; olmazsa None doner (Word yine de olusur)."""
    if not url:
        return None
    try:
        r = requests.get(url, timeout=timeout, headers={"User-Agent": "Mozilla/5.0"})
        ctype = r.headers.get("Content-Type", "")
        if r.status_code == 200 and ctype.startswith("image/") and "webp" not in ctype and r.content:
            return io.BytesIO(r.content)
    except requests.RequestException:
        pass
    return None


def _clean(text: str) -> str:
    # Word XML'de gecersiz kontrol karakterlerini temizle
    return "".join(ch for ch in (text or "") if ch in "\n\t" or ord(ch) >= 32)


def build_docx(posts, meta: dict, with_images: bool = True, mask=None) -> bytes:
    mask = mask or (lambda t: t)
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    doc.add_heading(f"#Data | #{meta.get('hashtag', '')} gonderi listesi", level=1)
    info = doc.add_paragraph()
    info.add_run(
        f"Kaynak: {meta.get('conn_name', '')}\n"
        f"Tarih araligi: {meta.get('start', '')} - {meta.get('end', '')}\n"
        f"Secim modu: {meta.get('mode', '')} | Seed: {meta.get('seed', '')}\n"
        f"Cekilme zamani: {meta.get('fetched_at', '')}\n"
        f"Gonderi sayisi: {len(posts)}"
    ).font.size = Pt(9)

    for i, p in enumerate(posts, 1):
        doc.add_heading(f"{i}. gonderi", level=2)

        if with_images:
            img = _download_image(p.media_url)
            if img is not None:
                try:
                    doc.add_picture(img, width=Inches(2.8))
                    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.LEFT
                except Exception:
                    doc.add_paragraph("(Gorsel eklenemedi)")
            elif p.media_url:
                doc.add_paragraph("(Gorsel indirilemedi; linkten bakilabilir)")

        kind = {"VIDEO": "Video", "CAROUSEL_ALBUM": "Coklu gorsel", "IMAGE": "Gorsel"}.get(p.media_type, p.media_type)
        line = doc.add_paragraph()
        r = line.add_run(f"{fmt_tr(p.created_at)}  |  {kind}  |  "
                         f"{p.likes} begeni  |  {p.comments} yorum")
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

        doc.add_paragraph(_clean(mask(p.caption)) or "(aciklama yok)")

        if p.permalink:
            lp = doc.add_paragraph("Link: ")
            _add_link(lp, p.permalink, p.permalink)

    note = doc.add_paragraph()
    note.add_run("Not: Kullanici kimlikleri listeye eklenmemistir. Orneklem, platformun eristirdigi "
                 "havuzdan secilmistir; hashtag'in tamami degildir.").italic = True

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


_KIND = {"VIDEO": "Video", "CAROUSEL_ALBUM": "Coklu gorsel", "IMAGE": "Gorsel", "TEXT": "Metin"}


def build_links_docx(details, comments, meta: dict, with_images: bool = True, mask=None) -> bytes:
    """Link analizi raporu: her gonderi icin icerik, metin, etkilesim ve altinda yorumlar."""
    mask = mask or (lambda t: t)
    by_post = {}
    for c in comments or []:
        by_post.setdefault(c.post_url, []).append(c)

    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    doc.add_heading(f"#Data | {meta.get('title', 'Link analizi')}", level=1)
    found = sum(1 for d in details if d.found)
    info = doc.add_paragraph()
    info.add_run(
        f"Olusturma zamani: {meta.get('fetched_at', '')}\n"
        f"Link sayisi: {len(details)} (bulunan: {found})\n"
        f"Yorum: {'gonderi basina en fazla ' + str(meta.get('per_post')) if meta.get('with_comments') else 'cekilmedi'}"
        f" | Toplam yorum: {len(comments or [])}"
    ).font.size = Pt(9)

    for i, d in enumerate(details, 1):
        plat = "Instagram" if d.platform == "instagram" else "X"
        doc.add_heading(f"{i}. {plat} gonderisi", level=2)
        if not d.found:
            p = doc.add_paragraph("Bu gonderi bulunamadi (silinmis, gizli veya erisilemiyor olabilir). Link: ")
            _add_link(p, d.url, d.url)
            continue
        if with_images:
            img = _download_image(d.media_url)
            if img is not None:
                try:
                    doc.add_picture(img, width=Inches(2.8))
                except Exception:
                    doc.add_paragraph("(Gorsel eklenemedi)")
            elif d.media_url:
                doc.add_paragraph("(Gorsel indirilemedi; linkten bakilabilir)")

        parts = [fmt_tr(d.created_at), _KIND.get(d.media_type, d.media_type),
                 f"{d.likes} begeni", f"{d.comments} yorum"]
        if d.platform == "x":
            parts += [f"{d.shares} repost", f"{d.quotes} alinti"]
        if d.views:
            parts.append(f"{d.views} goruntulenme")
        parts.append(f"toplam etkilesim {d.engagement}")
        r = doc.add_paragraph().add_run("  |  ".join(x for x in parts if x))
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

        doc.add_paragraph(_clean(mask(d.text)) or "(aciklama yok)")
        lp = doc.add_paragraph("Link: ")
        _add_link(lp, d.url, d.url)

        cs = by_post.get(d.url, [])
        if meta.get("with_comments"):
            doc.add_heading(f"Yorumlar ({len(cs)})", level=3)
            if not cs:
                doc.add_paragraph("(Yorum gelmedi)")
            for j, c in enumerate(cs, 1):
                cp = doc.add_paragraph()
                head = cp.add_run(f"{j}. {fmt_tr(c.created_at)} | {c.likes} begeni"
                                  + (" | yanit" if c.depth > 1 else "") + "  ")
                head.font.size = Pt(8)
                head.font.color.rgb = RGBColor(0x59, 0x59, 0x59)
                cp.add_run(_clean(mask(c.text)) or "(bos)")

    note = doc.add_paragraph()
    note.add_run("Not: Kullanici kimlikleri listeye eklenmemistir. Veriler Apify araclari uzerinden "
                 "toplanmistir; platformun gosterdigi kadarini kapsar.").italic = True
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
