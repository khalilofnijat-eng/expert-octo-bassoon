# LESSONS_LEARNED — Hatalar, kök nedenler, önlemler

Hatalar yalnızca not alınmaz; mümkün olanlar tekrarını yakalayacak testlere veya doğrulama kurallarına dönüştürülür (talep §8).

| Tarih | Olay | Kök neden | Önlem | Teste/kurala dönüştürüldü mü |
|---|---|---|---|---|
| 2026-09-27 | Alt agent'lar teslim raporunu dosya olarak yazamadı (ilk kez T-001'de görüldü; etkilenen teslimler: bkz. B-012). | Alt agent araç kısıtı; önceden bilinmiyordu. | Brief'lerde rapor dosyası beklenmez; kalıcı kayıt yöntemi sahip kararına bağlandı ([../BLOCKERS.md](../BLOCKERS.md) B-012). | Kurala dönüştürüldü ([../AGENTS.md](../AGENTS.md) §3; ayrıca [../tasks/README.md](../tasks/README.md) ve şablonlar) — T-011. |
| 2026-10-01 | Bulut oturumu kullanım sınırına takıldı; T-033b (T-035'in bağımsız doğrulaması) yarıda kaldı, diğer işler bekledi. | Uzun ve büyük görevler; ara sonuçlar commit edilmemişti. | Görevler küçük tutulur; her yeşil (testleri geçen) ara adım hemen commit ve push edilir. T-033b yerel oturumda yeniden çalıştırılır. | Kurala dönüştürüldü: [../LOCAL_SESSION_PROMPT.md](../LOCAL_SESSION_PROMPT.md) ve [../HANDOFF.md](../HANDOFF.md) uyarıları — T-044. |
