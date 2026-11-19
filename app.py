import os
from datetime import date, datetime, timedelta

import streamlit as st

from archive import Archive, ArchiveConnector
from connectors.bluesky import BlueskyConnector
from connectors.instagram_apify import InstagramApifyConnector
from connectors.instagram_graph import InstagramGraphConnector
from connectors.mastodon import MastodonConnector
from connectors.mock import MockConnector
from export_word import build_docx
from sampling import MODES, filter_by_date, select, to_dataframe

SRC_IG = "Instagram (Apify, hesapsiz)"
SRC_IG_GRAPH = "Instagram Graph API (resmi, hesap gerekir)"
SRC_MASTODON = "Mastodon (acik API, giris yok)"
SRC_BLUESKY = "Bluesky (acik API)"
SRC_ARCHIVE = "Kendi arsivimiz (SQLite)"
SRC_DEMO = "Demo (sahte veri)"


def _secret(name: str) -> str:
    """Anahtari once Streamlit secrets'tan, sonra ortam degiskeninden okur."""
    try:
        val = st.secrets.get(name, "")
    except Exception:
        val = ""
    return (val or os.environ.get(name, "")).strip()


st.set_page_config(page_title="Hashtag Veri Cekici", layout="wide")
st.title("Hashtag Veri Cekici")
st.caption("Akademik amacli prototip. Kullanici kimlikleri saklanmaz, yalnizca anonim kod tutulur.")

with st.sidebar:
    st.header("Ayarlar")
    platform = st.selectbox("Platform", ["Instagram", "X (yakinda)"])
    source = st.selectbox("Veri kaynagi", [SRC_IG, SRC_MASTODON, SRC_BLUESKY,
                                          SRC_IG_GRAPH, SRC_ARCHIVE, SRC_DEMO])
    hashtag = st.text_input("Hashtag", "girldate").lstrip("#").strip()
    today = date.today()
    start = st.date_input("Baslangic", today - timedelta(days=30))
    end = st.date_input("Bitis", today)
    n = st.number_input("Kac gonderi", 1, 5000, 20)
    mode_label = st.radio("Secim modu", list(MODES.keys()))
    seed = st.number_input("Seed (tekrarlanabilirlik)", 0, 10**9, 42)
    default_pool = 30 if source == SRC_IG else 500
    pool_limit = st.number_input("Havuz ust siniri (cekilecek en fazla gonderi)", 1, 20000, default_pool,
                                 help="Secim bu havuzdan yapilir. Apify'da her gonderi ucretsiz krediden duser.")

    apify_token = ""
    if source == SRC_IG:
        saved = _secret("APIFY_TOKEN")
        if saved:
            st.success("Apify anahtari kayitli.")
            apify_token = saved
        else:
            apify_token = st.text_input("Apify API anahtari", type="password",
                                        help="console.apify.com > Settings > API & Integrations")
        st.caption("Ucretsiz plan: her aramada en fazla ~30 gonderi.")

    ig_user, ig_token, feed = "", "", "recent_media"
    if source == SRC_IG_GRAPH:
        ig_user = st.text_input("IG User ID")
        ig_token = st.text_input("Access Token", type="password")
        feed = st.selectbox("Kaynak akisi", ["recent_media", "top_media"])

    save_arch = False
    if source in (SRC_IG, SRC_IG_GRAPH):
        save_arch = st.checkbox("Cekileni arsive de kaydet", value=True)

    bs_handle, bs_pass, arch_platform = "", "", "instagram"
    if source == SRC_BLUESKY:
        bs_handle = st.text_input("Bluesky handle (ornek: ad.bsky.social)")
        bs_pass = st.text_input("App Password", type="password")
    md_instance, md_local = "mastodon.social", False
    if source == SRC_MASTODON:
        md_instance = st.text_input("Mastodon sunucusu", "mastodon.social")
        md_local = st.checkbox("Sadece bu sunucunun yerel gonderileri", value=False)
    if source == SRC_ARCHIVE:
        arch_platform = st.selectbox("Arsivdeki platform", ["instagram", "bluesky", "mastodon"])

    go = st.button("Veriyi cek", type="primary")

if platform.startswith("X"):
    st.info("X baglayicisi henuz eklenmedi. Simdilik Instagram.")
    st.stop()

if go:
    if not hashtag:
        st.error("Hashtag bos olamaz.")
        st.stop()
    if start > end:
        st.error("Baslangic tarihi bitisten sonra olamaz.")
        st.stop()

    if source == SRC_DEMO:
        conn = MockConnector()
    elif source == SRC_IG:
        if not apify_token:
            st.error("Apify API anahtari gerekli.")
            st.stop()
        conn = InstagramApifyConnector(apify_token)
    elif source == SRC_IG_GRAPH:
        if not ig_user or not ig_token:
            st.error("User ID ve Access Token gerekli.")
            st.stop()
        conn = InstagramGraphConnector(ig_user, ig_token, feed)
    elif source == SRC_MASTODON:
        conn = MastodonConnector(md_instance, md_local)
    elif source == SRC_BLUESKY:
        if not bs_handle or not bs_pass:
            st.error("Bluesky handle ve App Password gerekli.")
            st.stop()
        conn = BlueskyConnector(bs_handle, bs_pass)
    else:
        conn = ArchiveConnector(arch_platform)

    try:
        with st.spinner("Cekiliyor... (Instagram'da 1-2 dakika surebilir)"):
            pool = conn.fetch(hashtag, start, end, int(pool_limit))
    except Exception as e:
        st.error(str(e))
        st.stop()

    if save_arch and pool:
        try:
            Archive().save(pool, hashtag)
        except Exception as e:
            st.warning(f"Arsive kaydedilemedi: {e}")

    in_range = filter_by_date(pool, start, end)
    chosen = select(in_range, MODES[mode_label], int(n), int(seed))
    st.session_state.pop("docx", None)
    st.session_state["result"] = {
        "conn_name": conn.name, "notes": list(conn.notes), "hashtag": hashtag,
        "start": start, "end": end, "mode": mode_label, "seed": int(seed),
        "pool": len(pool), "in_range": len(in_range),
        "chosen": chosen, "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }

res = st.session_state.get("result")
if not res:
    st.info("Soldan hashtag, tarih araligi ve gonderi sayisini secip **Veriyi cek** dugmesine bas.")
    st.stop()

chosen = res["chosen"]
df = to_dataframe(chosen)

with st.expander("Kaynak hakkinda notlar", expanded=False):
    for note in res["notes"]:
        st.write("- " + note)

c1, c2, c3 = st.columns(3)
c1.metric("Erisilen havuz", res["pool"])
c2.metric("Tarih araliginda", res["in_range"])
c3.metric("Listelenen", len(chosen))

if res["pool"] and not res["in_range"]:
    st.warning("Gonderiler geldi ama hicbiri secilen tarih araliginda degil. Araligi genislet.")

view = st.radio("Gorunum", ["Liste (icerik + metin + link)", "Tablo"], horizontal=True)

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
                st.markdown(f"**{i}.** {p.created_at[:16].replace('T', ' ')}  ·  "
                            f"{p.likes} begeni  ·  {p.comments} yorum")
                st.text(p.caption or "(aciklama yok)")
                if p.permalink:
                    st.markdown(f"[Gonderiye git]({p.permalink})")
else:
    st.dataframe(
        df, width="stretch",
        column_config={
            "permalink": st.column_config.LinkColumn("link"),
            "media_url": st.column_config.ImageColumn("onizleme"),
        },
    )

st.subheader("Disa aktar")
fname = f"{res['hashtag']}_{res['start']}_{res['end']}"
col_csv, col_word = st.columns(2)
with col_csv:
    st.download_button("CSV indir (Excel)", df.to_csv(index=False).encode("utf-8-sig"),
                       file_name=f"{fname}.csv", mime="text/csv")
with col_word:
    with_imgs = st.checkbox("Word'e gorselleri de ekle", value=True)
    if st.button("Word listesi hazirla"):
        with st.spinner("Word dosyasi hazirlaniyor..."):
            try:
                st.session_state["docx"] = build_docx(chosen, res, with_images=with_imgs)
            except Exception as e:
                st.session_state.pop("docx", None)
                st.error(f"Word dosyasi olusturulamadi: {e}")
    if st.session_state.get("docx"):
        st.download_button(
            "Word indir (.docx)", st.session_state["docx"], file_name=f"{fname}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        )

st.subheader("Yontem notu (makale icin)")
st.code(
    f"Kaynak: {res['conn_name']}\n"
    f"Hashtag: #{res['hashtag']}\n"
    f"Tarih araligi: {res['start']} - {res['end']}\n"
    f"Cekilme zamani: {res['fetched_at']}\n"
    f"Erisilen havuz: {res['pool']} | Aralikta: {res['in_range']} | Secilen: {len(chosen)}\n"
    f"Secim modu: {res['mode']} | Seed: {res['seed']}\n"
    f"Populerlik tanimi: begeni + yorum sayisi\n"
    f"Not: Orneklem, erisilebilen havuzdan secilmistir; evrenin tamami degildir.",
    language="text",
)
