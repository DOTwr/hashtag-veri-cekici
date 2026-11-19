import io
import os
from datetime import date, timedelta

import pandas as pd
import streamlit as st

from archive import Archive, ArchiveConnector
from connectors.bluesky import BlueskyConnector
from connectors.instagram_apify import InstagramApifyConnector
from connectors.instagram_graph import InstagramGraphConnector
from connectors.mastodon import MastodonConnector
from connectors.mock import MockConnector
from connectors.x_apify import XApifyConnector
from export_word import build_docx, build_links_docx
from merge import merge_posts, posts_from_csv
from sampling import MODES, filter_by_date, select, to_dataframe
from social import MAX_LINKS, analyze_links, estimate, mask_mentions, parse_links
from timeutil import fmt_tr, now_tr

APP_NAME = "#DATA - HASHTAGdata"

SRC_IG = "Instagram (Apify, hesapsiz)"
SRC_X = "X / Twitter (Apify, hesapsiz)"
SRC_MASTODON = "Mastodon (acik API, giris yok)"
SRC_BLUESKY = "Bluesky (acik API)"
SRC_IG_GRAPH = "Instagram Graph API (resmi, hesap gerekir)"
SRC_ARCHIVE = "Kendi arsivimiz (SQLite)"
SRC_DEMO = "Demo (sahte veri)"
APIFY_SOURCES = (SRC_IG, SRC_X)


def _secret(name: str) -> str:
    try:
        val = st.secrets.get(name, "")
    except Exception:
        val = ""
    return (val or os.environ.get(name, "")).strip()


st.set_page_config(page_title=APP_NAME, page_icon="#", layout="wide")

# ------------------------------------------------------------------ yan menu
with st.sidebar:
    st.markdown(f"## {APP_NAME}")
    st.caption("Akademik amacli veri toplama araci.")
    saved_token = _secret("APIFY_TOKEN")
    if saved_token:
        st.success("Apify anahtari kayitli.")
        apify_token = saved_token
    else:
        apify_token = st.text_input(
            "Apify API anahtari", type="password",
            help="console.apify.com > Settings > API & Integrations. Kaydedilmez; sayfa kapaninca silinir.")
    st.caption("Instagram ve X icin gerekir. Ucretsiz plan: ayda 5 USD kredi.")
    hide_mentions = st.checkbox("Metinlerdeki @kullanici adlarini gizle", value=True,
                                help="Anonimlik icin aciklama ve yorumlardaki @ad ifadeleri @kullanici olarak gosterilir.")

mask = mask_mentions if hide_mentions else (lambda t: t)


def _progress_cb(placeholder):
    def cb(status, secs):
        placeholder.caption(f"Apify calisiyor... ({status}, {secs} sn)")
    return cb


st.title(APP_NAME)
st.caption("Kullanici kimlikleri saklanmaz, yalnizca anonim kod tutulur. Saatler Turkiye saatidir.")

tab_tag, tab_one, tab_bulk = st.tabs(["# Hashtag", "Gonderi yorumlari", "Toplu link analizi"])

# ================================================================== 1) HASHTAG
with tab_tag:
    with st.form("hashtag_form"):
        c1, c2 = st.columns(2)
        with c1:
            source = st.selectbox("Platform / veri kaynagi", [SRC_IG, SRC_X, SRC_MASTODON, SRC_BLUESKY,
                                                              SRC_IG_GRAPH, SRC_ARCHIVE, SRC_DEMO])
            hashtag = st.text_input("Hashtag", "girldate")
            today = date.today()
            d1, d2 = st.columns(2)
            start = d1.date_input("Baslangic", today - timedelta(days=30))
            end = d2.date_input("Bitis", today)
        with c2:
            n = st.number_input("Kac gonderi listelensin", 1, 5000, 20)
            mode_label = st.radio("Secim modu", list(MODES.keys()), horizontal=True)
            s1, s2 = st.columns(2)
            seed = s1.number_input("Seed (tekrarlanabilirlik)", 0, 10**9, 42)
            pool_limit = s2.number_input("Havuz ust siniri", 1, 20000, 30,
                                         help="Cekilecek en fazla gonderi. Instagram ucretsiz planda ~30 ile sinirli.")

        with st.expander("Ek ayarlar (onceki cekimleri birlestirme, diger kaynaklar)"):
            st.markdown("**Daha fazla gonderi icin onceki cekimleri birlestir.** Ucretsiz planda her aramada "
                        "~30 Instagram gonderisi gelir. Farkli gunlerde indirdigin CSV'leri buraya yuklersen "
                        "hepsi tek havuzda birlesir, ayni gonderi iki kez sayilmaz.")
            old_csvs = st.file_uploader("Onceki CSV ciktilari", type=["csv"], accept_multiple_files=True)
            use_history = st.checkbox("Apify'da sakli onceki Instagram cekimlerimi de ekle (ayni hashtag)",
                                      value=False)
            st.divider()
            ig_user = st.text_input("IG User ID (sadece Graph API)")
            ig_token = st.text_input("IG Access Token (sadece Graph API)", type="password")
            feed = st.selectbox("Graph API akisi", ["recent_media", "top_media"])
            bs_handle = st.text_input("Bluesky handle (sadece Bluesky)")
            bs_pass = st.text_input("Bluesky App Password", type="password")
            md_instance = st.text_input("Mastodon sunucusu", "mastodon.social")
            md_local = st.checkbox("Sadece bu sunucunun yerel gonderileri", value=False)
            arch_platform = st.selectbox("Arsivdeki platform", ["instagram", "x", "bluesky", "mastodon"])
            save_arch = st.checkbox("Cekileni bu oturumun arsivine de kaydet", value=False)

        go = st.form_submit_button("Veriyi cek", type="primary")

    if go:
        hashtag = hashtag.lstrip("#").strip()
        err = None
        if not hashtag:
            err = "Hashtag bos olamaz."
        elif start > end:
            err = "Baslangic tarihi bitisten sonra olamaz."
        elif source in APIFY_SOURCES and not apify_token:
            err = "Bu kaynak icin soldaki menuye Apify API anahtarini gir."
        elif source == SRC_IG_GRAPH and (not ig_user or not ig_token):
            err = "Graph API icin Ek ayarlar'da User ID ve Access Token gerekli."
        elif source == SRC_BLUESKY and (not bs_handle or not bs_pass):
            err = "Bluesky icin Ek ayarlar'da handle ve App Password gerekli."
        if err:
            st.error(err)
        else:
            prog = st.empty()
            cb = _progress_cb(prog)
            conn = {
                SRC_DEMO: lambda: MockConnector(),
                SRC_IG: lambda: InstagramApifyConnector(apify_token, include_history=use_history, on_progress=cb),
                SRC_X: lambda: XApifyConnector(apify_token, on_progress=cb),
                SRC_IG_GRAPH: lambda: InstagramGraphConnector(ig_user, ig_token, feed),
                SRC_MASTODON: lambda: MastodonConnector(md_instance, md_local),
                SRC_BLUESKY: lambda: BlueskyConnector(bs_handle, bs_pass),
                SRC_ARCHIVE: lambda: ArchiveConnector(arch_platform),
            }[source]()
            try:
                with st.spinner("Cekiliyor... (Instagram/X'te 1-2 dakika surebilir)"):
                    fresh = conn.fetch(hashtag, start, end, int(pool_limit))
            except Exception as e:
                st.error(str(e))
                fresh = None
            prog.empty()

            if fresh is not None:
                old, merged_files = [], 0
                for f in old_csvs or []:
                    try:
                        old.extend(posts_from_csv(f.getvalue()))
                        merged_files += 1
                    except ValueError as e:
                        st.warning(f"{f.name}: {e}")
                pool = merge_posts(old, fresh)        # yeni cekim sayilari gunceller
                if save_arch and fresh:
                    try:
                        Archive().save(fresh, hashtag)
                    except Exception as e:
                        st.warning(f"Arsive kaydedilemedi: {e}")
                in_range = filter_by_date(pool, start, end)
                chosen = select(in_range, MODES[mode_label], int(n), int(seed))
                st.session_state.pop("tag_docx", None)
                st.session_state["tag_res"] = {
                    "conn_name": conn.name, "notes": list(conn.notes), "hashtag": hashtag,
                    "start": start, "end": end, "mode": mode_label, "seed": int(seed),
                    "fresh": len(fresh), "merged_files": merged_files, "pool": len(pool),
                    "in_range": len(in_range), "chosen": chosen,
                    "fetched_at": now_tr().strftime("%Y-%m-%d %H:%M (Turkiye saati)"),
                }

    res = st.session_state.get("tag_res")
    if not res:
        st.info("Hashtag, tarih araligi ve gonderi sayisini secip **Veriyi cek** dugmesine bas.")
    else:
        chosen = res["chosen"]
        df = to_dataframe(chosen)
        df["created_at"] = df["created_at"].map(fmt_tr)
        df["caption"] = df["caption"].map(mask)

        with st.expander("Kaynak hakkinda notlar"):
            for note in res["notes"]:
                st.write("- " + note)
        m1, m2, m3, m4 = st.columns(4)
        m1.metric("Bu cekimde gelen", res["fresh"])
        m2.metric("Birlesik havuz", res["pool"])
        m3.metric("Tarih araliginda", res["in_range"])
        m4.metric("Listelenen", len(chosen))
        if res["merged_files"]:
            st.caption(f"{res['merged_files']} onceki CSV birlestirildi; tekrar eden gonderiler bir kez sayildi.")
        if res["pool"] and not res["in_range"]:
            st.warning("Gonderiler geldi ama hicbiri secilen tarih araliginda degil. Araligi genislet.")

        view = st.radio("Gorunum", ["Liste (icerik + metin + link)", "Tablo"], horizontal=True, key="tag_view")
        if view.startswith("Liste"):
            for i, p in enumerate(chosen, 1):
                with st.container(border=True):
                    left, right = st.columns([1, 2])
                    with left:
                        if p.media_url:
                            try:
                                st.image(p.media_url, width="stretch")
                            except Exception:
                                st.caption("Onizleme yuklenemedi.")
                        else:
                            st.caption("Gorsel yok")
                        if p.media_type == "VIDEO":
                            st.caption("Video gonderi (izlemek icin linke tikla)")
                        elif p.media_type == "CAROUSEL_ALBUM":
                            st.caption("Coklu gorsel (tamami icin linke tikla)")
                    with right:
                        st.markdown(f"**{i}.** {fmt_tr(p.created_at)}  ·  {p.likes} begeni  ·  {p.comments} yorum")
                        st.text(mask(p.caption) or "(aciklama yok)")
                        if p.permalink:
                            st.markdown(f"[Gonderiye git]({p.permalink})")
        else:
            st.dataframe(df, width="stretch", column_config={
                "permalink": st.column_config.LinkColumn("link"),
                "media_url": st.column_config.ImageColumn("onizleme"),
            })

        st.subheader("Disa aktar")
        fname = f"{res['hashtag']}_{res['start']}_{res['end']}"
        raw_df = to_dataframe(chosen)               # CSV: birlestirmeye uygun ham bicim
        raw_df["caption"] = raw_df["caption"].map(mask)
        e1, e2 = st.columns(2)
        with e1:
            st.download_button("CSV indir (Excel / sonra birlestirmek icin)",
                               raw_df.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"{fname}.csv", mime="text/csv")
        with e2:
            with_imgs = st.checkbox("Word'e gorselleri de ekle", value=True, key="tag_imgs")
            if st.button("Word listesi hazirla", key="tag_word"):
                with st.spinner("Word dosyasi hazirlaniyor..."):
                    try:
                        st.session_state["tag_docx"] = build_docx(chosen, res, with_images=with_imgs, mask=mask)
                    except Exception as e:
                        st.session_state.pop("tag_docx", None)
                        st.error(f"Word dosyasi olusturulamadi: {e}")
            if st.session_state.get("tag_docx"):
                st.download_button("Word indir (.docx)", st.session_state["tag_docx"], file_name=f"{fname}.docx",
                                   mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document")

        st.subheader("Yontem notu (makale icin)")
        st.code(
            f"Kaynak: {res['conn_name']}\n"
            f"Hashtag: #{res['hashtag']}\n"
            f"Tarih araligi: {res['start']} - {res['end']}\n"
            f"Cekilme zamani: {res['fetched_at']}\n"
            f"Bu cekim: {res['fresh']} | Birlestirilen onceki dosya: {res['merged_files']} | "
            f"Havuz: {res['pool']} | Aralikta: {res['in_range']} | Secilen: {len(chosen)}\n"
            f"Secim modu: {res['mode']} | Seed: {res['seed']}\n"
            f"Populerlik tanimi: begeni + yorum sayisi\n"
            f"Not: Orneklem, erisilebilen havuzdan secilmistir; evrenin tamami degildir.",
            language="text",
        )


# ------------------------------------------------------------------ ortak: link raporu gosterimi
def _details_df(details):
    rows = []
    for d in details:
        rows.append({
            "platform": "Instagram" if d.platform == "instagram" else "X",
            "bulundu": "evet" if d.found else "hayir",
            "tarih": fmt_tr(d.created_at),
            "metin": mask(d.text),
            "begeni": d.likes, "yorum": d.comments, "repost": d.shares, "alinti": d.quotes,
            "goruntulenme": d.views, "toplam_etkilesim": d.engagement,
            "medya_turu": d.media_type, "onizleme": d.media_url,
            "link": d.url, "yazar_kodu": d.author_hash,
        })
    return pd.DataFrame(rows, columns=["platform", "bulundu", "tarih", "metin", "begeni", "yorum", "repost",
                                       "alinti", "goruntulenme", "toplam_etkilesim", "medya_turu", "onizleme",
                                       "link", "yazar_kodu"])


def _comments_df(comments):
    rows = [{
        "gonderi_link": c.post_url, "tarih": fmt_tr(c.created_at), "yorum": mask(c.text),
        "begeni": c.likes, "yanit_sayisi": c.replies, "tur": "yanit" if c.depth > 1 else "yorum",
        "yorum_link": c.url, "yazar_kodu": c.author_hash,
    } for c in comments]
    return pd.DataFrame(rows, columns=["gonderi_link", "tarih", "yorum", "begeni", "yanit_sayisi", "tur",
                                       "yorum_link", "yazar_kodu"])


def _excel(details_df, comments_df) -> bytes:
    buf = io.BytesIO()
    with pd.ExcelWriter(buf, engine="openpyxl") as xw:
        details_df.to_excel(xw, sheet_name="gonderiler", index=False)
        comments_df.to_excel(xw, sheet_name="yorumlar", index=False)
    return buf.getvalue()


def _show_report(rep, key: str, title: str):
    details, comments = rep["details"], rep["comments"]
    found = [d for d in details if d.found]
    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Bulunan gonderi", f"{len(found)} / {len(details)}")
    k2.metric("Toplam begeni", sum(d.likes for d in found))
    k3.metric("Toplam yorum (sayac)", sum(d.comments for d in found))
    k4.metric("Cekilen yorum", len(comments))
    missing = [d.url for d in details if not d.found]
    if missing:
        with st.expander(f"Bulunamayan {len(missing)} link"):
            st.caption("Silinmis, gizli hesap veya erisilemeyen gonderiler olabilir.")
            for u in missing:
                st.write(u)

    ddf, cdf = _details_df(details), _comments_df(comments)
    by_post = {}
    for c in comments:
        by_post.setdefault(c.post_url, []).append(c)

    if len(details) == 1:
        d = details[0]
        if d.found:
            with st.container(border=True):
                left, right = st.columns([1, 2])
                with left:
                    if d.media_url:
                        try:
                            st.image(d.media_url, width="stretch")
                        except Exception:
                            st.caption("Onizleme yuklenemedi.")
                    else:
                        st.caption("Gorsel yok")
                with right:
                    extra = f"  ·  {d.shares} repost  ·  {d.quotes} alinti" if d.platform == "x" else ""
                    views = f"  ·  {d.views} goruntulenme" if d.views else ""
                    st.markdown(f"{fmt_tr(d.created_at)}  ·  {d.likes} begeni  ·  {d.comments} yorum{extra}{views}")
                    st.text(mask(d.text) or "(aciklama yok)")
                    st.markdown(f"[Gonderiye git]({d.url})")
    else:
        st.dataframe(ddf, width="stretch", column_config={
            "link": st.column_config.LinkColumn("link"),
            "onizleme": st.column_config.ImageColumn("onizleme"),
        })

    if rep["with_comments"]:
        st.subheader("Yorumlar")
        if not comments:
            st.info("Yorum gelmedi. Gonderide yorum olmayabilir ya da yorumlar kapali olabilir.")
        else:
            choices = ["Tum gonderiler"] + [d.url for d in found if by_post.get(d.url)]
            pick = st.selectbox("Hangi gonderinin yorumlari", choices, key=f"{key}_pick") if len(found) > 1 else choices[0]
            sel = comments if pick == "Tum gonderiler" else by_post.get(pick, [])
            sort = st.radio("Sirala", ["En cok begenilen", "En yeni", "En eski"], horizontal=True, key=f"{key}_sort")
            if sort == "En cok begenilen":
                sel = sorted(sel, key=lambda c: c.likes, reverse=True)
            else:
                sel = sorted(sel, key=lambda c: c.created_at, reverse=(sort == "En yeni"))
            direct = sum(1 for c in sel if c.depth <= 1)
            st.caption(f"{len(sel)} yorum ({direct} dogrudan yorum, {len(sel) - direct} yanit). "
                       f"Ortalama begeni: {round(sum(c.likes for c in sel) / max(len(sel), 1), 1)}")
            for j, c in enumerate(sel[:300], 1):
                with st.container(border=True):
                    tag = " · yanit" if c.depth > 1 else ""
                    st.caption(f"{j}. {fmt_tr(c.created_at)} · {c.likes} begeni · {c.replies} yanit{tag}")
                    st.text(mask(c.text) or "(bos)")
            if len(sel) > 300:
                st.caption(f"Ekranda ilk 300 yorum gosteriliyor; tamami ({len(sel)}) dosyalarda var.")

    st.subheader("Disa aktar")
    fname = f"{key}_{now_tr().strftime('%Y%m%d_%H%M')}"
    x1, x2, x3 = st.columns(3)
    with x1:
        st.download_button("Excel indir (gonderiler + yorumlar)", _excel(ddf, cdf), file_name=f"{fname}.xlsx",
                           mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet", key=f"{key}_xlsx")
    with x2:
        st.download_button("Gonderiler CSV", ddf.to_csv(index=False).encode("utf-8-sig"),
                           file_name=f"{fname}_gonderiler.csv", mime="text/csv", key=f"{key}_csv1")
        if rep["with_comments"]:
            st.download_button("Yorumlar CSV", cdf.to_csv(index=False).encode("utf-8-sig"),
                               file_name=f"{fname}_yorumlar.csv", mime="text/csv", key=f"{key}_csv2")
    with x3:
        imgs = st.checkbox("Word'e gorselleri de ekle", value=len(details) <= 30, key=f"{key}_imgs")
        if st.button("Word raporu hazirla", key=f"{key}_wordbtn"):
            with st.spinner("Word dosyasi hazirlaniyor..."):
                try:
                    st.session_state[f"{key}_docx"] = build_links_docx(details, comments, {
                        "title": title, "fetched_at": rep["fetched_at"],
                        "with_comments": rep["with_comments"], "per_post": rep["per_post"],
                    }, with_images=imgs, mask=mask)
                except Exception as e:
                    st.session_state.pop(f"{key}_docx", None)
                    st.error(f"Word dosyasi olusturulamadi: {e}")
        if st.session_state.get(f"{key}_docx"):
            st.download_button("Word indir (.docx)", st.session_state[f"{key}_docx"], file_name=f"{fname}.docx",
                               mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                               key=f"{key}_docxdl")


def _run_report(links, with_comments, per_post, key):
    prog = st.empty()
    try:
        with st.spinner("Cekiliyor... (link sayisina gore birkac dakika surebilir)"):
            rep = analyze_links(apify_token, links, with_comments, int(per_post), _progress_cb(prog))
    except Exception as e:
        prog.empty()
        st.error(str(e))
        return
    prog.empty()
    st.session_state.pop(f"{key}_docx", None)
    st.session_state[f"{key}_res"] = {
        "details": rep.details, "comments": rep.comments, "with_comments": with_comments,
        "per_post": int(per_post), "fetched_at": now_tr().strftime("%Y-%m-%d %H:%M (Turkiye saati)"),
    }


# ================================================================== 2) TEK GONDERI YORUMLARI
with tab_one:
    st.markdown("Bir **Instagram** veya **X** gonderisinin linkini yapistir; gonderinin bilgileri ve "
                "altindaki yorumlar ayristirilir.")
    with st.form("one_form"):
        one_link = st.text_input("Gonderi linki", placeholder="https://x.com/kullanici/status/123...  veya  "
                                                              "https://www.instagram.com/p/ABC123/")
        one_n = st.number_input("En fazla kac yorum", 1, 2000, 100)
        one_go = st.form_submit_button("Yorumlari cek", type="primary")
    if one_go:
        links, _bad = parse_links(one_link)
        if not links:
            st.error("Gecerli bir Instagram (instagram.com/p/... veya /reel/...) ya da X (x.com/.../status/...) "
                     "gonderi linki bulunamadi.")
        elif not apify_token:
            st.error("Soldaki menuye Apify API anahtarini gir.")
        else:
            st.caption(f"Tahmini maliyet: ~{estimate(links[:1], int(one_n), True):.3f} USD (ucretsiz krediden)")
            _run_report(links[:1], True, one_n, "one")
    if st.session_state.get("one_res"):
        _show_report(st.session_state["one_res"], "one", "Gonderi yorumlari")

# ================================================================== 3) TOPLU LINK ANALIZI
with tab_bulk:
    st.markdown(f"Elindeki gonderi linklerini (en fazla **{MAX_LINKS}**, Instagram ve X karisik olabilir) yapistir. "
                "Her biri icin aciklama, begeni, yorum sayisi ve etkilesim cikarilir; istersen yorumlar da cekilir.")
    with st.form("bulk_form"):
        bulk_text = st.text_area("Linkler (her satira bir link)", height=200)
        bulk_file = st.file_uploader("veya link listesi dosyasi (.txt / .csv)", type=["txt", "csv"])
        b1, b2 = st.columns(2)
        bulk_comments = b1.checkbox("Yorumlari da cek", value=True)
        bulk_n = b2.number_input("Gonderi basina en fazla yorum", 1, 500, 20)
        bulk_go = st.form_submit_button("Linkleri analiz et", type="primary")
    if bulk_go:
        text = bulk_text or ""
        if bulk_file is not None:
            text += "\n" + bulk_file.getvalue().decode("utf-8-sig", errors="ignore")
        links, bad = parse_links(text)
        if bad:
            st.warning(f"Taninmayan {len(bad)} satir atlandi: " + ", ".join(bad[:5]) + (" ..." if len(bad) > 5 else ""))
        if not links:
            st.error("Gecerli Instagram veya X gonderi linki bulunamadi.")
        elif len(links) > MAX_LINKS:
            st.error(f"En fazla {MAX_LINKS} link analiz edilebilir; {len(links)} link girildi.")
        elif not apify_token:
            st.error("Soldaki menuye Apify API anahtarini gir.")
        else:
            ig = sum(1 for l in links if l.platform == "instagram")
            st.caption(f"{len(links)} link ({ig} Instagram, {len(links) - ig} X). Tahmini maliyet: "
                       f"~{estimate(links, int(bulk_n), bulk_comments):.2f} USD (ucretsiz krediden).")
            _run_report(links, bulk_comments, bulk_n, "bulk")
    if st.session_state.get("bulk_res"):
        _show_report(st.session_state["bulk_res"], "bulk", "Toplu link analizi")
