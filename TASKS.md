# TASKS — Görevler ve durumları

Görev durumunun **tek kaynağı** bu dosyadır. Görev kayıt sistemi: [tasks/README.md](tasks/README.md). Aşamalar: [docs/PLAN.md](docs/PLAN.md). Engeller: [BLOCKERS.md](BLOCKERS.md).

Durum değerleri: `planlandı` · `sürüyor` · `teslim edildi — Main Agent incelemesi bekliyor` · `kabul edildi` · `düzeltme istendi` · `engelli`

| ID | Başlık | Aşama | Sahip (agent rolü) | Bağımlılık | Durum | Brief | Rapor |
|---|---|---|---|---|---|---|---|
| T-001 | Ortam ve erişim keşfi | 1 | Keşif agent'ı | — | kabul edildi | [brief](tasks/T-001/brief.md) | rapor kaydı bekliyor — sahip kararı (B-012) |
| T-002 | Avito resmî entegrasyon araştırması | 1 | Araştırma agent'ı | — | kabul edildi | [brief](tasks/T-002/brief.md) | rapor kaydı bekliyor — sahip kararı (B-012) |
| T-003 | Kalıcı kayıt düzeni iskeleti | 2 | Dokümantasyon agent'ı | — | kabul edildi | [brief](tasks/T-003/brief.md) | [rapor](tasks/T-003/report.md) |
| T-004 | Mimari taslağı (teknoloji seçimi keşif sonrası) | 2 | Mimari agent'ı | T-001, T-002 | sürüyor (Mimari agent'ı) | [brief](tasks/T-004/brief.md) | — |
| T-005 | Kayıt düzeninin bağımsız incelemesi | 2 | İnceleme agent'ı | T-009 | planlandı | [brief](tasks/T-005/brief.md) | — |
| T-006 | Avito geçmiş konuşmalarının salt okunur aktarımı | 3 | — | B-001/B-007 + T-010 | engelli | — | — |
| T-007 | Depo/muhasebe sistemi keşfi ve salt okunur bağlantı | 1/5 | — | B-002 | engelli | — | — |
| T-008 | Obsidian Vault yerleşimi ve senkronizasyon kontrolü | 10 | — | B-003 | engelli | — | — |
| T-009 | T-001/T-002 bulgularının ortak kayıtlara işlenmesi | 2 | Dokümantasyon agent'ı | T-001, T-002 | kabul edildi | [brief](tasks/T-009/brief.md) | Main Agent'a metin olarak teslim edildi (B-012) |
| T-010 | Salt okunur Avito geçmiş derinlik ölçüm betiği (GET-only, chatRead yok) | 3 | — | B-007, B-009, B-011 | planlandı | — | — |
| T-011 | Görev kurallarının B-012'ye uyarlanması (rapor metin olarak teslim) | 2 | Dokümantasyon agent'ı | T-009 | teslim edildi — Main Agent incelemesi bekliyor | [brief](tasks/T-011/brief.md) | Main Agent'a metin olarak teslim edildi (B-012) |

Not: Alt agent'lar rapor dosyası yazamadığı için T-001, T-002, T-009 ve T-011 raporları repoda yok; kalıcı kayıt yöntemi sahip kararını bekliyor ([BLOCKERS.md](BLOCKERS.md) B-012). Kabul edilen bulgular ilgili kayıtlara işlendi: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md), [docs/NOTES.md](docs/NOTES.md), [docs/DECISIONS.md](docs/DECISIONS.md), [BLOCKERS.md](BLOCKERS.md).
