# Hashtag Veri Çekici (akademik prototip)

Bir hashtag için belirli bir tarih aralığındaki gönderileri çeker. Açıklama metni, tarih, beğeni/yorum sayısı ve gönderi linkini tablo olarak gösterir ve CSV olarak indirmenizi sağlar. Akademik çalışmalar için geliştirilmiştir.

## Özellikler
- Hashtag, tarih aralığı ve gönderi sayısı seçimi
- Seçim modları: **en popüler** (beğeni + yorum), **rastgele** (seed ile tekrarlanabilir), **en yeni**
- Kullanıcı kimlikleri saklanmaz, yalnızca geri döndürülemez anonim kod tutulur
- Her çekim için otomatik **yöntem notu** (kaynak, tarih aralığı, havuz büyüklüğü, seed)
- CSV dışa aktarma (Excel'de Türkçe karakterler bozulmaz)
- Word (.docx) liste çıktısı: her gönderi için görsel, tarih, beğeni/yorum, açıklama metni ve tıklanabilir link

## Veri kaynakları
| Kaynak | Hesap gerekir mi? | Not |
|---|---|---|
| Instagram (Apify) | Instagram hesabı gerekmez; ücretsiz Apify API anahtarı gerekir | Instagram'ın gösterdiği gönderiler; ücretsiz planda ayda ~2.000 gönderi. |
| Mastodon | Hayır | Kronolojik, kişiselleştirilmemiş hashtag akışı. Yalnızca seçilen sunucunun gördüğü gönderiler gelir. |
| Demo | Hayır | Sahte veri, arayüzü denemek için. |
| Bluesky | Evet (App Password) | Arama API'si giriş istiyor. |
| Instagram Graph API | Evet (Business hesap + token) | Yalnızca son 24 saat; "top" sıralaması algoritmiktir. |
| Kendi arşivimiz (SQLite) | Hayır | Daha önce kaydedilen çekimler. |

## Yöntem açısından sınırlılıklar
- Örneklem, platformun erişime açtığı havuzdan seçilir; hashtag evreninin tamamı değildir.
- Mastodon'da sonuçlar seçilen sunucuya bağlıdır.
- Instagram için geriye dönük keyfi tarih aralığı resmi API ile alınamaz.

## Bilgisayarda çalıştırma (Windows)
`baslat.bat` dosyasına çift tıklayın. Python'u bulur, paketleri kurar ve uygulamayı tarayıcıda açar.

Elle çalıştırmak için:
```
pip install -r requirements.txt
streamlit run app.py
```

## Web sitesi olarak yayınlama
Bu depo [Streamlit Community Cloud](https://streamlit.io/cloud) ile ücretsiz yayınlanabilir. Ana dosya: `app.py`.
Notlar:
- Bulutta `arsiv.db` kalıcı değildir; uygulama yeniden başladığında silinir.
- Apify anahtarını sitede saklamak için **Settings → Secrets** bölümüne `APIFY_TOKEN = "anahtar"` satırını ekleyin. Anahtarı asla koda veya GitHub'a yazmayın.
- Anonimleştirme için kendi gizli tuzunuzu belirleyin: Streamlit Cloud'da uygulamanın **Settings → Secrets** bölümüne `ANON_SALT = "uzun-rastgele-bir-metin"` satırını ekleyin.

## Testler
```
python test_core.py
python test_new.py
python test_mastodon.py
python test_instagram_apify.py
python test_word.py
```
