# TASKS — Görevler ve durumları

Görev durumunun **tek kaynağı** bu dosyadır; başka kayıtlar görev durumunu tekrar etmez, buraya bağlantı verir. Görev kayıt sistemi: [tasks/README.md](tasks/README.md). Aşamalar: [docs/PLAN.md](docs/PLAN.md). Engeller: [BLOCKERS.md](BLOCKERS.md).

Durum değerleri: `planlandı` · `sürüyor` · `teslim edildi — Main Agent incelemesi bekliyor` · `teslim edildi — <inceleme görevi> bağımsız incelemesi sürüyor` · `kabul edildi` · `düzeltmelerle kabul edildi` · `düzeltme istendi` · `engelli`

Sıradaki görev kimliği: **T-014** (uygulama dalgası buradan başlar).

| ID | Başlık | Aşama | Sahip (agent rolü) | Bağımlılık | Durum | Brief | Teslim |
|---|---|---|---|---|---|---|---|
| T-001 | Ortam ve erişim keşfi | 1 | Keşif agent'ı | — | kabul edildi | [brief](tasks/T-001/brief.md) | metin (B-012 listesi); özet: [INTEGRATIONS §2](docs/INTEGRATIONS.md) |
| T-002 | Avito resmî entegrasyon araştırması | 1 | Araştırma agent'ı | — | kabul edildi | [brief](tasks/T-002/brief.md) | metin (B-012 listesi); özet: [INTEGRATIONS §3–§6](docs/INTEGRATIONS.md), [NOTES](docs/NOTES.md) |
| T-003 | Kalıcı kayıt düzeni iskeleti | 2 | Dokümantasyon agent'ı | — | kabul edildi | [brief](tasks/T-003/brief.md) | [rapor](tasks/T-003/report.md) |
| T-004 | Mimari taslağı (teknoloji seçimi keşif sonrası) | 2 | Mimari agent'ı | T-001, T-002 | teslim edildi — T-012 bağımsız incelemesi sürüyor | [brief](tasks/T-004/brief.md) | metin (B-012 listesi); çıktı: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| T-005 | Kayıt düzeninin bağımsız incelemesi | 2 | İnceleme agent'ı | T-009 | düzeltmelerle kabul edildi (düzeltme görevi: T-013) | [brief](tasks/T-005/brief.md) | metin (B-012 listesi) |
| T-006 | Avito geçmiş konuşmalarının salt okunur aktarımı | 3 | — | API yolu (D-011): B-007, B-009, B-011 + T-010. Tarayıcı yedeği (yalnızca API'nin ulaşamadığı eski geçmiş için): ayrıca B-001 | engelli | — | — |
| T-007 | Depo/muhasebe sistemi keşfi ve salt okunur bağlantı | 1/5 | — | B-002 | engelli | — | — |
| T-008 | Obsidian Vault yerleşimi ve senkronizasyon kontrolü | 10 | — | B-003 | engelli | — | — |
| T-009 | T-001/T-002 bulgularının ortak kayıtlara işlenmesi | 2 | Dokümantasyon agent'ı | T-001, T-002 | kabul edildi | [brief](tasks/T-009/brief.md) | metin (B-012 listesi) |
| T-010 | Salt okunur Avito geçmiş derinlik ölçüm betiği (GET-only, chatRead yok) | 3 | — | B-007, B-009, B-011 | planlandı | — (kabul ölçütleri aşağıda) | — |
| T-011 | Görev kurallarının B-012'ye uyarlanması (rapor metin olarak teslim) | 2 | Dokümantasyon agent'ı | T-009 | kabul edildi | [brief](tasks/T-011/brief.md) | metin (B-012 listesi) |
| T-011b | Mimari taslağının commit edilmesi (commit `667d96d`) | 2 | kayıtta yok | T-004 | kabul edildi | — | metin (B-012 listesi) |
| T-012 | Mimari taslağının bağımsız incelemesi | 2 | İnceleme agent'ı | T-004, T-011b | sürüyor | — | — |
| T-013 | T-005 bulgularının düzeltilmesi (kayıtlar, `.gitignore`, AGENTS eklemeleri, D-014) | 2 | Dokümantasyon agent'ı | T-005 | teslim edildi — Main Agent incelemesi bekliyor | — | metin |

## T-010 kabul ölçütleri (brief yazılana kadar)

- [ ] Yalnızca GET çağrıları; `chatRead` ve yazan hiçbir çağrı yapılmaz (D-012, [AGENTS.md](AGENTS.md) §6).
- [ ] Okundu yan etkisi canlı olarak doğrulanır.

## B-012 listesi — repoda olmayan teslim metinleri

Bu liste [BLOCKERS.md](BLOCKERS.md) B-012'nin **tek** listesidir; diğer kayıtlar "bkz. B-012" der. Metinler Main Agent'tadır (oturum scratchpad'indeki kopyalar geçicidir). Kabul edilen bulgular ilgili kayıtlara işlendi.

| Görev | Kabul edilen bulguların kalıcı yeri |
|---|---|
| T-001 | [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §2, [BLOCKERS.md](BLOCKERS.md) |
| T-002 | [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §3–§6, [docs/NOTES.md](docs/NOTES.md), [docs/DECISIONS.md](docs/DECISIONS.md) D-011–D-013, [BLOCKERS.md](BLOCKERS.md) |
| T-004 | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) (taslak, T-012 incelemesinde) |
| T-005 | T-013 düzeltmeleri ([CHANGELOG.md](CHANGELOG.md) → T-013 kaydı) |
| T-009 | Git geçmişi (`9b4bdc1`) |
| T-011 | Git geçmişi (`fb13470`) |
| T-011b | Git geçmişi (`667d96d`) |

Her yeni metin teslimi kabul edildiğinde bu listeye eklenir.
