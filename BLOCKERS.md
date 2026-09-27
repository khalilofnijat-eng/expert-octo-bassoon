# BLOCKERS — Engeller ve gereken müdahaleler

Engellerin **tek kaynağı** bu dosyadır. Durum değerleri: `açık` · `kısmen çözüldü` · `çözüldü`.

| ID | Başlık | Etki | Gereken müdahale (kimden) | Durum | Açılış |
|---|---|---|---|---|---|
| B-001 | Avito hesabının açık olduğu Chrome'a erişim yok | Geçmiş konuşma aktarımı (T-006) başlayamaz. Bu oturum bulut konteynerde çalışıyor ve tarayıcı kontrol aracı görünmüyor (T-001 doğruluyor). | Sahip, Chrome'un çalıştığı bilgisayarı bildirmeli; o bilgisayarda yetkili erişim kurulmalı (yöntem Main Agent tarafından sahibe iletildi). | açık | 2026-09-27 |
| B-002 | Depo/muhasebe yazılımı, erişim biçimi ve ürün fotoğraflarının yeri bilinmiyor | Ürün/stok/fiyat/fotoğraf sorgusu ve eşleştirme (T-007, aşama 5) başlayamaz. | Sahip: yazılımın adı, çalıştığı yer, erişim biçimi ve fotoğrafların konumu. | açık | 2026-09-27 |
| B-003 | Obsidian Vault yolu ve senkronizasyon yöntemi bilinmiyor | Vault yerleşimi ve senkronizasyon kontrolü (T-008) başlayamaz. | Sahip: Vault yolu ve kullanılan senkronizasyon yöntemi. | açık | 2026-09-27 |
| B-004 | 7/24 çalışacak bilgisayar/sunucu belirlenmedi | Üretim kurulumu, izleme ve 7/24 tasarımının somutlaştırılması bekler. | Sahip: sürekli açık bilgisayar veya sunucu bilgisi. | açık | 2026-09-27 |
| B-005 | İşletme kuralları bilinmiyor (fiyat, indirim sınırı, teslimat, ödeme, rezervasyon, iade/garanti, insana devir) | Teklif/sipariş akışı ve asistan kuralları tanımlanamaz. | Sahip: mevcut kurallar. | açık | 2026-09-27 |
| B-006 | AI hizmeti tercihi ve bütçe sınırı bilinmiyor | Model hizmeti seçimi ve maliyet sınırları belirlenemez. | Sahip: tercih (varsa) ve bütçe sınırı. | açık | 2026-09-27 |
| B-007 | Avito API erişim koşulları ve hesabın API erişimi belirsiz | Üretim bağlantı yönteminin seçimi bekler. | T-002 araştırıyor; sahipten hesap türü bilgisi gerekebilir. | açık | 2026-09-27 |
| B-008 | GitHub deposunun (khalilofnijat-eng/expert-octo-bassoon) bu proje için kullanılacağı sahip tarafından onaylanmadı | Deponun kalıcı proje deposu olarak kullanımı teyitsiz; görünürlüğü (özel/açık) T-001 doğruluyor. | Sahip: depo onayı; T-001: görünürlük doğrulaması. | açık | 2026-09-27 |
