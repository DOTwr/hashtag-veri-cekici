"""Apify araclarini calistirmak icin ortak yardimci.

Calistirma -> bitmesini bekleme -> sonuc listesini alma. Uzun isler (100 link gibi)
5 dakikalik senkron siniri asmasin diye asenkron calistirilir.
"""
import time

import requests

API = "https://api.apify.com/v2"
FINAL = {"SUCCEEDED", "FAILED", "TIMED-OUT", "ABORTED"}

# Aracin adi -> (aciklama, 1000 sonuc basina yaklasik ucret USD)
ACTORS = {
    "ig_hashtag": ("apify~instagram-hashtag-scraper", 2.60),
    "ig_posts": ("apify~instagram-scraper", 2.70),
    "ig_comments": ("apify~instagram-comment-scraper", 2.60),
    "x_posts": ("xquik~x-tweet-scraper", 0.15),
    "x_replies": ("xquik~x-reply-scraper", 0.15),
}


def estimate_cost(kind: str, n_results: int) -> float:
    return ACTORS[kind][1] * max(n_results, 0) / 1000.0


def _check(r: requests.Response):
    if r.status_code == 401:
        raise RuntimeError("Apify API anahtari gecersiz. Settings > API & Integrations sayfasindan kontrol et.")
    if r.status_code == 402:
        raise RuntimeError("Apify ucretsiz kredisi bu ay doldu. Ay basinda yenilenir.")
    if r.status_code == 403:
        raise RuntimeError(f"Apify bu islemi reddetti (403): {r.text[:200]}")
    if r.status_code not in (200, 201):
        raise RuntimeError(f"Apify hatasi ({r.status_code}): {r.text[:200]}")


def _get(url, token, **kw):
    try:
        r = requests.get(url, headers={"Authorization": f"Bearer {token}"}, timeout=90, **kw)
    except requests.Timeout:
        raise RuntimeError("Apify yanit vermedi (zaman asimi). Biraz sonra tekrar dene.")
    except requests.RequestException:
        raise RuntimeError("Apify'a baglanilamadi. Internet baglantini kontrol et.")
    _check(r)
    return r


def run_actor(token: str, kind: str, run_input: dict, max_wait_s: int = 900,
              on_progress=None) -> list:
    """Araci calistirir, bitmesini bekler ve sonuc satirlarini dondurur."""
    token = (token or "").strip()
    if not token:
        raise RuntimeError("Apify API anahtari gerekli.")
    actor = ACTORS[kind][0]

    try:
        r = requests.post(f"{API}/acts/{actor}/runs",
                          headers={"Authorization": f"Bearer {token}"},
                          json=run_input, timeout=60)
    except requests.Timeout:
        raise RuntimeError("Apify yanit vermedi (zaman asimi). Biraz sonra tekrar dene.")
    except requests.RequestException:
        raise RuntimeError("Apify'a baglanilamadi. Internet baglantini kontrol et.")
    _check(r)
    run = (r.json() or {}).get("data") or {}
    run_id = run.get("id")
    if not run_id:
        raise RuntimeError("Apify calistirmayi baslatamadi.")

    started = time.time()
    status = run.get("status", "")
    while status not in FINAL:
        if time.time() - started > max_wait_s:
            raise RuntimeError("Apify islemi cok uzun surdu. Daha az link veya daha kucuk sayiyla tekrar dene.")
        if on_progress:
            on_progress(status, int(time.time() - started))
        run = (_get(f"{API}/actor-runs/{run_id}", token, params={"waitForFinish": 30}).json() or {}).get("data") or {}
        status = run.get("status", "")

    if status != "SUCCEEDED":
        raise RuntimeError(f"Apify islemi basarisiz oldu (durum: {status}).")

    ds = run.get("defaultDatasetId")
    if not ds:
        return []
    items = _get(f"{API}/datasets/{ds}/items", token, params={"clean": "true", "format": "json"}).json()
    if not isinstance(items, list):
        raise RuntimeError("Apify'dan beklenmeyen bir yanit geldi.")
    return [it for it in items if isinstance(it, dict)]


def past_runs_items(token: str, kind: str, match_input, limit: int = 50) -> list:
    """Hesaptaki onceki basarili calistirmalardan, girdisi match_input(dict)->True olanlarin
    sonuclarini toplar (Apify'in sakladigi sure boyunca)."""
    token = (token or "").strip()
    if not token:
        raise RuntimeError("Apify API anahtari gerekli.")
    actor = ACTORS[kind][0]
    runs = (_get(f"{API}/acts/{actor}/runs", token,
                 params={"desc": "true", "limit": limit, "status": "SUCCEEDED"}).json() or {}).get("data", {})
    out = []
    for run in runs.get("items", []):
        if run.get("status") not in (None, "SUCCEEDED"):
            continue
        kvs, ds = run.get("defaultKeyValueStoreId"), run.get("defaultDatasetId")
        if not kvs or not ds:
            continue
        try:
            inp = _get(f"{API}/key-value-stores/{kvs}/records/INPUT", token).json()
        except RuntimeError:
            continue           # silinmis veya erisilemeyen kayit
        if not isinstance(inp, dict) or not match_input(inp):
            continue
        try:
            items = _get(f"{API}/datasets/{ds}/items", token, params={"clean": "true", "format": "json"}).json()
        except RuntimeError:
            continue
        if isinstance(items, list):
            out.extend(it for it in items if isinstance(it, dict))
    return out
