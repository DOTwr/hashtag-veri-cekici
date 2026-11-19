"""Secilen gonderileri Word (.docx) listesi olarak disa aktarir."""
import io

import requests
from docx import Document
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.opc.constants import RELATIONSHIP_TYPE
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor


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


def build_docx(posts, meta: dict, with_images: bool = True) -> bytes:
    doc = Document()
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    doc.add_heading(f"#{meta.get('hashtag', '')} gonderi listesi", level=1)
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
        r = line.add_run(f"{(p.created_at or '')[:16].replace('T', ' ')}  |  {kind}  |  "
                         f"{p.likes} begeni  |  {p.comments} yorum")
        r.font.size = Pt(9)
        r.font.color.rgb = RGBColor(0x59, 0x59, 0x59)

        doc.add_paragraph(_clean(p.caption) or "(aciklama yok)")

        if p.permalink:
            lp = doc.add_paragraph("Link: ")
            _add_link(lp, p.permalink, p.permalink)

    note = doc.add_paragraph()
    note.add_run("Not: Kullanici kimlikleri listeye eklenmemistir. Orneklem, platformun eristirdigi "
                 "havuzdan secilmistir; hashtag'in tamami degildir.").italic = True

    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
