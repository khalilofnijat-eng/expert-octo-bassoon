# TASKS — Görevler ve durumları

Görev durumunun **tek kaynağı** bu dosyadır. Görev kayıt sistemi: [tasks/README.md](tasks/README.md). Aşamalar: [docs/PLAN.md](docs/PLAN.md). Engeller: [BLOCKERS.md](BLOCKERS.md).

Durum değerleri: `planlandı` · `sürüyor` · `teslim edildi — Main Agent incelemesi bekliyor` · `kabul edildi` · `düzeltme istendi` · `engelli`

| ID | Başlık | Aşama | Sahip (agent rolü) | Bağımlılık | Durum | Brief | Rapor |
|---|---|---|---|---|---|---|---|
| T-001 | Ortam ve erişim keşfi | 1 | Keşif agent'ı | — | sürüyor | [brief](tasks/T-001/brief.md) | `tasks/T-001/report.md` (teslim bekleniyor) |
| T-002 | Avito resmî entegrasyon araştırması | 1 | Araştırma agent'ı | — | sürüyor | [brief](tasks/T-002/brief.md) | `tasks/T-002/report.md` (teslim bekleniyor) |
| T-003 | Kalıcı kayıt düzeni iskeleti | 2 | Dokümantasyon agent'ı | — | teslim edildi — Main Agent incelemesi bekliyor | [brief](tasks/T-003/brief.md) | [rapor](tasks/T-003/report.md) |
| T-004 | Mimari taslağı (teknoloji seçimi keşif sonrası) | 2 | Mimari agent'ı | T-001, T-002 | planlandı | — | — |
| T-005 | Kayıt düzeninin bağımsız incelemesi | 2 | İnceleme agent'ı | T-003 | planlandı | — | — |
| T-006 | Avito geçmiş konuşmalarının salt okunur aktarımı | 3 | — | T-002, B-001 | engelli | — | — |
| T-007 | Depo/muhasebe sistemi keşfi ve salt okunur bağlantı | 1/5 | — | B-002 | engelli | — | — |
| T-008 | Obsidian Vault yerleşimi ve senkronizasyon kontrolü | 10 | — | B-003 | engelli | — | — |

Not: T-001/T-002 rapor dosyaları henüz teslim edilmediği için bağlantı yerine yol olarak yazıldı; teslimde bağlantıya çevrilecek.
