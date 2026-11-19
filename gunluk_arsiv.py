"""Her gun calistirilir: Instagram'dan son 24 saatin gonderilerini cekip arsive kaydeder.

Kullanim:
    set IG_USER_ID=...        (Windows)
    set IG_ACCESS_TOKEN=...
    python gunluk_arsiv.py girldate
"""
import os
import sys
from datetime import date, timedelta

from archive import Archive
from connectors.instagram_graph import InstagramGraphConnector


def main():
    if len(sys.argv) < 2:
        sys.exit("Kullanim: python gunluk_arsiv.py <hashtag>")
    tag = sys.argv[1]
    uid, tok = os.environ.get("IG_USER_ID"), os.environ.get("IG_ACCESS_TOKEN")
    if not uid or not tok:
        sys.exit("IG_USER_ID ve IG_ACCESS_TOKEN ortam degiskenleri gerekli.")
    conn = InstagramGraphConnector(uid, tok, "recent_media")
    posts = conn.fetch(tag, date.today() - timedelta(days=1), date.today(), 2000)
    n = Archive().save(posts, tag)
    print(f"#{tag}: {n} gonderi arsive islendi.")


if __name__ == "__main__":
    main()
