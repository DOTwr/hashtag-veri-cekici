# #DATA - HASHTAGdata

Akademik çalışmalar için sosyal medya veri toplama aracı. Instagram ve X (Twitter) için kendi hesabınızı kullanmadan, anonim olarak veri toplar.

**Site:** https://hashtag-veri-cekici.streamlit.app

## Bölümler

### 1. Hashtag
Platform, hashtag, tarih aralığı ve gönderi sayısı seçilir. Gönderiler **içerik + açıklama + link** olarak alt alta listelenir.
- Seçim modları: **en popüler** (beğeni + yorum), **rastgele** (seed ile tekrarlanabilir), **en yeni**
- **Önceki çekimleri birleştirme:** Ücretsiz planda Instagram her aramada ~30 gönderi verir. Farklı günlerde indirilen CSV'ler yüklenince tek havuzda birleşir; aynı gönderi iki kez sayılmaz. İsteğe bağlı olarak Apify'da saklı önceki çekimler de eklenebilir.
- Otomatik **yöntem notu** (makale için)

### 2. Gönderi yorumları
Tek bir Instagram veya X gönderi linki yapıştırılır. Gönderinin bilgileri (açıklama, beğeni, yorum, repost, görüntülenme) ve altındaki yorumlar (yanıtlar dahil) ayrıştırılır.

### 3. Toplu link analizi
En fazla **100 link** (Instagram ve X karışık) yapıştırılır veya .txt/.csv olarak yüklenir. Her gönderi için açıklama, beğeni, yorum sayısı ve toplam etkileşim çıkarılır; isteğe bağlı olarak yorumlar da çekilir.

## Çıktılar
- **Excel** (gönderiler + yorumlar ayrı sayfalarda), **CSV**
- **Word** raporu: her gönderi için görsel, tarih, etkileşim, metin, link ve altında yorumlar

## Anonimlik
- Kullanıcı adları ve kimlikleri saklanmaz; yalnızca geri döndürülemez anonim kod (`yazar_kodu`) tutulur.
- Metinlerdeki `@kullaniciadi` ifadeleri varsayılan olarak `@kullanici` olarak gizlenir.
- X yorum linkleri kullanıcı adı içermeyen biçimde (`x.com/i/web/status/...`) verilir.

## Veri kaynakları
| Kaynak | Ne gerekir | Not |
|---|---|---|
| Instagram (Apify) | Ücretsiz Apify API anahtarı | Instagram hesabı gerekmez. Ücretsiz planda her aramada ~30 gönderi. |
| X / Twitter (Apify) | Ücretsiz Apify API anahtarı | X hesabı gerekmez. Hashtag + tarih aralığıyla arama. |
| Mastodon | Hiçbir şey | Açık API, kronolojik. |
| Bluesky | Bluesky App Password | Arama girişi gerektirir. |
| Demo | Hiçbir şey | Sahte veri, deneme için. |

Yaklaşık ücretler (Apify ücretsiz kredisinden, ayda 5 USD): Instagram gönderi ~2,70 USD / 1000, Instagram yorum ~2,60 USD / 1000, X gönderi ve yanıt ~0,15 USD / 1000. Uygulama her işlemden önce tahmini maliyeti gösterir.

## Yöntem açısından sınırlılıklar
- Veriler platformların gösterdiği kadarını kapsar; hashtag evreninin tamamı değildir.
- Instagram ve X verileri üçüncü parti bir servis (Apify) aracılığıyla toplanır; makalenin yöntem bölümünde belirtilmelidir.
- Saatler Türkiye saatidir (UTC+3).

## Apify anahtarını sitede saklamak (isteğe bağlı)
Streamlit Cloud'da uygulamanın **Settings → Secrets** bölümüne `APIFY_TOKEN = "anahtar"` eklenir. Anahtar koda veya GitHub'a yazılmaz. Bu durumda siteyi yalnızca izin verilen kişilerin görebileceği şekilde kısıtlamak önerilir.

## Bilgisayarda çalıştırma (Windows)
`baslat.bat` dosyasına çift tıklayın. Elle: `pip install -r requirements.txt` ve `streamlit run app.py`.

## Testler
```
python test_core.py
python test_new.py
python test_mastodon.py
python test_instagram_apify.py
python test_social.py
python test_merge_time_word.py
python test_word.py
python test_app.py
```
