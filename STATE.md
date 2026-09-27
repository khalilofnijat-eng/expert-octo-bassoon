# STATE — Projenin mevcut gerçek durumu

**Son güncelleme:** 2026-09-27 (T-036, Dokümantasyon agent'ı)

Görev durumları burada tekrar edilmez: **[TASKS.md](TASKS.md)**. Engeller: [BLOCKERS.md](BLOCKERS.md). Kararlar: [docs/DECISIONS.md](docs/DECISIONS.md).

## Şu anki durum

| Konu | Durum |
|---|---|
| Aşama | 2 (kayıt düzeni ve mimari) tamamlandı. 3 (geçmiş aktarımı): okuma istemcisi ve mock hazır, ölçüm ve aktarım engelli. 5, 6, 7, 9: uygulama yalnızca sentetik veriyle sürüyor — bkz. [docs/PLAN.md](docs/PLAN.md) |
| Mimari | **Kabul edildi ve commit edildi** (rev.2, `1f7c2dc`; sahip onayı 2026-09-27, B-013 çözüldü). Kararlar D-015–D-035. |
| Uygulama kodu | İskelet + PII maskeleyici, output filter, çekirdek DB/kuyruk/kilitler/CAS, Avito okuma istemcisi + mock, metin gönderim istemcisi, inventory portu + sentetik adaptör + fitment. Hangi görevin kabul edildiği: [TASKS.md](TASKS.md). Tüm CI çalıştırmaları başarılı; **yalnızca sentetik testler**, gerçek sistemde test yok: [docs/TEST_REPORT.md](docs/TEST_REPORT.md). |
| Bağlı dış sistem | Yok. Avito üretim kanalı resmî Messenger API (D-011), ama bağlı değil; bu ortamdan avito.ru'ya erişim yok (B-009). Messenger API tarifesi için sahibe sunulan seçenekler: D-042. Ayrıntı: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) |
| Toplanan Avito verisi | Yok. İlk adım salt okunur ölçüm (T-010, [brief](tasks/T-010/brief.md)). |
| Asistan modu | Taslak (asistan henüz yok; canlı yetki verilmedi — D-006) |
| Sahip cevapları | B-013 çözüldü; B-005 kısmen (ödeme yöntemleri D-039, ИП, Avito Доставка). Diğerleri ve 2026-09-27'de gönderilen yeni soru grubu: [BLOCKERS.md](BLOCKERS.md) "Sahibe soruldu" sütunu. |
| Avito kuralları | Sistem Avito moderasyonunu atlatacak biçimde tasarlanmaz (D-040). Meşru alternatifler araştırıldı (T-037, [docs/NOTES.md](docs/NOTES.md)). |
| Web sitesi | Ayrı proje, bu projenin kapsamı dışında (D-041); başlangıç dosyaları `website-kickoff/` (T-038). |
| GitHub | Geliştirme dalı D-014; depo görünürlüğü ve kullanımı sahip onayı bekliyor (B-008) |
| Çalışma ortamı | Geçici bulut konteyner; sahibin bilgisayarı değil (B-001). Sahibin bilgisayarında yerel kurulum: T-039. |

## Sıradaki eylem

1. Sahip cevapları — özellikle B-002 (depo/muhasebe yazılımı; gerçek stok, fiyat ve fotoğraf için en büyük engel), B-004 (7/24 çalışacak makine), B-005'in kalanı, B-008; poisk.vin (B-015) ve Avito desteği mektuplarını sahip gönderir (T-040).
2. Sürenlerin teslimi ve kararları: T-018, T-034, T-033b, T-039, T-040; T-016, T-036 teslimlerinin değerlendirilmesi; T-018b'nin durumu.
3. Engelsiz sentetik görevler (bağımlılıkları kabul edilmiş): T-020, T-021, T-026.

Ayrıntılı adımlar ve uyarılar: [HANDOFF.md](HANDOFF.md).
