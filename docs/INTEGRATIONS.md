# INTEGRATIONS — Bağlantılar ve yetenekler

Her yetenek güven etiketiyle yazılır. "Doğrulanmış" yalnızca kanıtı (komut çıktısı, test kaydı) olan yetenek içindir; resmî belge kopyasından alınan ama canlı denenmemiş yetenekler "resmî spec kopyası — canlı doğrulanmadı" diye işaretlenir. Engeller: [../BLOCKERS.md](../BLOCKERS.md). Görevler: [../TASKS.md](../TASKS.md). Kararlar: [DECISIONS.md](DECISIONS.md).

Kaynak notu: T-001 ve T-002 raporları Main Agent tarafından kabul edildi, ancak repoda dosya olarak yok (kalıcı kaydı [B-012](../BLOCKERS.md)).

| Entegrasyon | Amaç | Yöntem | Durum | Yetenekler | Kanıt | Engel |
|---|---|---|---|---|---|---|
| Avito resmî API (Messenger + Items) | Yeni mesaj alma, yetkili gönderim, geçmiş okuma, ilan bilgisi | Resmî REST API, OAuth2 `client_credentials`; webhook + periyodik uzlaştırma (D-011); kendi ince istemcimiz (D-013) | seçildi, bağlı değil | Aşağıdaki liste — **hiçbiri canlı doğrulanmadı** | T-002 raporu; resmî spec'in GitHub kopyaları (ör. [MissiaL/avito-api](https://github.com/MissiaL/avito-api), commit 8e9bafc9) | B-007, B-009, B-011 |
| Avito web arayüzü / Chrome | Yalnızca API'nin ulaşamadığı eski geçmiş için, tek seferlik (D-011) | Sahibin bilgisayarındaki oturum — BİLİNMİYOR | erişim yok | — | T-001 raporu (araç yok) | B-001 |
| Depo / muhasebe sistemi | Ürün, stok, fiyat, rezervasyon, sipariş | BİLİNMİYOR | bilinmiyor | — | — | B-002 |
| Ürün fotoğrafları | Gerçek stok kaydına bağlı fotoğraflar | BİLİNMİYOR | bilinmiyor | — | — | B-002 |
| Obsidian Vault | Proje belgelerinin son yerleşimi | BİLİNMİYOR | bilinmiyor | — | — | B-003 |
| GitHub | Kod ve geliştirme sürümleme | Git, HTTPS remote | çalışıyor; depo **public**; 2026-09-27 itibarıyla varsayılan dal `claude/youthful-goldberg-l427nm` ve depodaki tek dal bu (`main` dalı yok) | Doğrulanmış: okuma ve push | 2026-09-27, T-011: GitHub API `search_repositories` → `default_branch: "claude/youthful-goldberg-l427nm"`, `visibility: "public"`, `private: false`; `list_branches` → yalnızca `claude/youthful-goldberg-l427nm` (sha `9b4bdc1`). Önceki gözlem (T-001, ilk push'tan önce, depo boşken): `default_branch: main`. | B-008 |
| Bulut geliştirme ortamı | Kod geliştirme, birim testleri | Geçici bulut konteyner | çalışıyor; **avito.ru engelli** (403) | Doğrulanmış: Python 3.11, Node 22, Docker, PostgreSQL/Redis istemcileri, headless Playwright/Chromium; PyPI, npm, GitHub ve Anthropic API'ye ağ erişimi. Doğrulanmış olumsuz: www/api/developers.avito.ru erişilemiyor | T-001 raporu (komut çıktıları) | B-009 |
| AI hizmeti | Cevap taslağı üretimi | BİLİNMİYOR | seçilmedi | — | — | B-006, B-010 |

## Avito resmî API — yetenekler (T-002)

Tümü **resmî spec kopyası — canlı doğrulanmadı**, aksi belirtilmedikçe. Base URL `https://api.avito.ru`. Uç nokta ayrıntıları T-002 raporundadır (B-012).

- Token: OAuth2 `client_credentials` (satıcının kendi hesabı); belgelenen ömür 24 saat, bir örnekte 3600 sn — yanıttaki `expires_in` esas alınmalı.
- Sohbet listesi (filtre: ilan, okunmamış, sohbet türü; `limit` < 100 + `offset`) ve sohbet bilgisi (ilan bağlamı: id, başlık, fiyat metni, url, küçük ana görsel).
- Mesaj okuma (`limit` < 100 + `offset`); okumak sohbeti okundu yapmaz ([NOTES.md](NOTES.md)).
- Metin gönderme (en fazla 1000 karakter).
- Görsel gönderme: önce yükleme (JPEG/HEIC/GIF/BMP/PNG, ≤ 24 MB, istek başına 1 görsel), sonra `image_id` ile gönderme. Dosya/video gönderme belgelenmemiş.
- Mesaj silme (gönderimden en geç 1 saat içinde).
- Sohbeti okundu yapma (`chatRead`) — ayrı çağrı.
- Webhook: abone olma, listeleme, abonelikten çıkma; kayıtlı URL 2 saniyede 200 OK dönmeli.
- Kara liste; sesli mesaj dosyalarını okuma (gönderme belgelenmemiş); Avito sistem/otomatik yanıt mesajlarını okuma.
- İlanlar: kendi ilanlarını listeleme (dakikada 25 istek); tek ilan bilgisi kısmi (başlık, fiyat, fotoğraf dönmez; dakikada 500 istek); Autoload ID eşlemesi.
- **Belirsiz / doğrulanamadı:** geçmişin ne kadar geriye okunabildiği (T-010 ölçecek, D-012); Messenger uçlarının hız sınırı; webhook imza algoritması (topluluk: `x-avito-messenger-signature`, ikincil), tekrar deneme ve teslim garantisi; ilanın tam fotoğraf setini döndüren uç; API kullanım şartlarının metni.
- **Erişim şartı:** ücretli abonelik ve ana hesap anahtarı — bkz. [../BLOCKERS.md](../BLOCKERS.md) B-007.
