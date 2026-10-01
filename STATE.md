# STATE — Projenin mevcut gerçek durumu

**Son güncelleme:** 2026-10-01 (T-044, bulut aşamasının sonu; Dokümantasyon agent'ı)

Görev durumları burada tekrar edilmez: **[TASKS.md](TASKS.md)**. Engeller: [BLOCKERS.md](BLOCKERS.md). Kararlar: [docs/DECISIONS.md](docs/DECISIONS.md).

## Şu anki durum

| Konu | Durum |
|---|---|
| Aşama | 2 (kayıt düzeni ve mimari) tamamlandı. 3 (geçmiş aktarımı): okuma istemcisi ve mock hazır, ölçüm ve aktarım engelli. 5, 6, 7, 9: uygulama yalnızca sentetik veriyle sürüyor — bkz. [docs/PLAN.md](docs/PLAN.md) |
| Mimari | **Kabul edildi ve commit edildi** (rev.2, `1f7c2dc`; sahip onayı 2026-09-27, B-013 çözüldü). Kararlar D-015–D-035. |
| Uygulama kodu | İskelet + PII maskeleyici, output filter (T-041 tipli span'lar), çekirdek DB/kuyruk/kilitler/CAS, Avito okuma istemcisi + mock, metin gönderim istemcisi, inventory portu + sentetik adaptör + fitment; Windows kimlik bilgisi kurulumu ve salt okunur erişim kontrolü (T-039); salt okunur Vault taraması (T-043). Kabuller: [TASKS.md](TASKS.md). **Yalnızca sentetik testler**, gerçek sistemde test yok: [docs/TEST_REPORT.md](docs/TEST_REPORT.md). |
| Bağlı dış sistem | Yok. Avito üretim kanalı resmî Messenger API (D-011), ama bağlı değil; bu ortamdan avito.ru'ya erişim yok (B-009). Tarife: sahip Базовый'da API olmadığını teyit etti, «Расширенный»'e geçecek; API erişimi T-039 erişim kontrolüyle canlı doğrulanacak (B-007, D-042). Ayrıntı: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) |
| Toplanan Avito verisi | Yok. İlk adım salt okunur ölçüm (T-010, [brief](tasks/T-010/brief.md)). |
| Asistan modu | Taslak (asistan henüz yok; canlı yetki verilmedi — D-006) |
| Sahip cevapları | B-013 çözüldü; B-005 kısmen (ödeme yöntemleri D-039, ИП, Avito Доставка); B-002 kısmen (stok, fiyat, fotoğraf sahibin Obsidian Vault'unda; D-046); B-004 kısmen (pilot sahibin Windows bilgisayarında; D-045); B-001, B-007, B-011 cevaplandı, T-039 kurulumuyla kapanacak. Sahip hesap türü, tarife ve erişimin **tekrar sorulmamasını** istedi ([AGENTS.md](AGENTS.md) §6). Kalanlar: [BLOCKERS.md](BLOCKERS.md). |
| Avito kuralları | Sistem Avito moderasyonunu atlatacak biçimde tasarlanmaz (D-040). Meşru alternatifler araştırıldı (T-037, [docs/NOTES.md](docs/NOTES.md)). |
| Web sitesi | Ayrı proje, bu projenin kapsamı dışında (D-041); başlangıç dosyaları `website-kickoff/` (T-038). |
| GitHub | Geliştirme dalı D-014; depo görünürlüğü ve kullanımı sahip onayı bekliyor (B-008) |
| Çalışma ortamı | Geliştirme: geçici bulut konteyner; sahibin bilgisayarına ulaşamaz (B-001). Pilot: sahibin Windows bilgisayarı, Windows servisleri, yalnızca poller, yönetim ekranı yalnızca localhost (D-045). **Bulut aşaması bitti:** iş, sahibin bilgisayarındaki yerel oturumda sürer — [docs/VAULT_PLACEMENT.md](docs/VAULT_PLACEMENT.md), [LOCAL_SESSION_PROMPT.md](LOCAL_SESSION_PROMPT.md). |

## Sıradaki eylem

Yerel oturumda, bu sırayla ([LOCAL_SESSION_PROMPT.md](LOCAL_SESSION_PROMPT.md)):

0. Ortam doğrulaması: git, uv, Python 3.11, PostgreSQL 16 (Windows; kurulum planı sahip onayıyla), clone ve dala push yetkisi.
1. Sahip [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) ile gizli değer kurulumunu ve erişim kontrolünü çalıştırır; sonuç «Расширенный» / «Максимальный» çelişkisini çözer (B-007, D-042).
2. Vault taraması (T-043 betiği, salt okunur) → salt okunur Vault `InventoryPort` adaptörünün tasarımı (D-046).
3. Bağımsız incelemeler: T-033b (yeniden) ve T-045 (T-041 doğrulaması).
4. T-010 salt okunur geçmiş derinlik ölçümü (çalışan Messenger API gerekir).
5. Sentetik konuşma akışı T-020, T-021, T-023; sonra T-024.
6. Windows servisleri ve yalnızca poller modu (D-045).

Sahibin bekleyen işleri: mektupları göndermek (`docs/letters/`), depoyu özel yapmak (B-008), +%10 için muhasebeci teyidi (D-039), tarife değişikliği.

Ayrıntılı adımlar ve uyarılar: [HANDOFF.md](HANDOFF.md).
