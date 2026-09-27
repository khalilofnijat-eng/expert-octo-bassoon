# TASKS — Görevler ve durumları

Görev durumunun **tek kaynağı** bu dosyadır; başka kayıtlar görev durumunu tekrar etmez, buraya bağlantı verir. Görev kayıt sistemi: [tasks/README.md](tasks/README.md). Aşamalar: [docs/PLAN.md](docs/PLAN.md). Engeller: [BLOCKERS.md](BLOCKERS.md).

Durum değerleri: `planlandı` · `sürüyor` · `teslim edildi — Main Agent incelemesi bekliyor` · `teslim edildi — <inceleme görevi> bağımsız incelemesi sürüyor` · `kabul edildi` · `düzeltmelerle kabul edildi` · `düzeltme istendi` · `engelli`

Sıradaki görev kimliği: **T-041**.

## Keşif, kayıt düzeni ve mimari

| ID | Başlık | Aşama | Sahip (agent rolü) | Bağımlılık | Durum | Brief | Teslim |
|---|---|---|---|---|---|---|---|
| T-001 | Ortam ve erişim keşfi | 1 | Keşif agent'ı | — | kabul edildi | [brief](tasks/T-001/brief.md) | metin (B-012 listesi); özet: [INTEGRATIONS §2](docs/INTEGRATIONS.md) |
| T-002 | Avito resmî entegrasyon araştırması | 1 | Araştırma agent'ı | — | kabul edildi | [brief](tasks/T-002/brief.md) | metin (B-012 listesi); özet: [INTEGRATIONS §3–§6](docs/INTEGRATIONS.md), [NOTES](docs/NOTES.md) |
| T-003 | Kalıcı kayıt düzeni iskeleti | 2 | Dokümantasyon agent'ı | — | kabul edildi | [brief](tasks/T-003/brief.md) | [rapor](tasks/T-003/report.md) |
| T-004 | Mimari (teknoloji seçimi keşif sonrası) | 2 | Mimari agent'ı | T-001, T-002 | kabul edildi (rev.2) ve commit edildi (`1f7c2dc`, T-036; sahip onayı 2026-09-27, B-013 kapandı) | [brief](tasks/T-004/brief.md) | metin, rev.1 ve rev.2 (B-012 listesi); çıktı: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) rev.2 (`1f7c2dc`; rev.1 `667d96d`); kararlar: [DECISIONS](docs/DECISIONS.md) D-015–D-035 |
| T-005 | Kayıt düzeninin bağımsız incelemesi | 2 | İnceleme agent'ı | T-009 | düzeltmelerle kabul edildi (düzeltme görevi: T-013) | [brief](tasks/T-005/brief.md) | metin (B-012 listesi) |
| T-006 | Avito geçmiş konuşmalarının salt okunur aktarımı | 3 | — | API yolu (D-011): B-007, B-009, B-011 + T-010. Tarayıcı yedeği (yalnızca API'nin ulaşamadığı eski geçmiş için): ayrıca B-001 | engelli | — | — |
| T-007 | Depo/muhasebe sistemi keşfi ve salt okunur bağlantı | 1/5 | — | B-002 | engelli | — | — |
| T-008 | Obsidian Vault yerleşimi ve senkronizasyon kontrolü | 10 | — | B-003 | engelli | — | — |
| T-009 | T-001/T-002 bulgularının ortak kayıtlara işlenmesi | 2 | Dokümantasyon agent'ı | T-001, T-002 | kabul edildi | [brief](tasks/T-009/brief.md) | metin (B-012 listesi) |
| T-010 | Salt okunur Avito geçmiş derinlik ölçüm betiği (GET-only, `chatRead` yok; sahibin makinesinde) | 3 | — | T-016, T-017, B-007, B-009, B-011 | engelli (B-007, B-009, B-011 açık; T-017 kabul edildi) | [brief](tasks/T-010/brief.md) | — |
| T-011 | Görev kurallarının B-012'ye uyarlanması (rapor metin olarak teslim) | 2 | Dokümantasyon agent'ı | T-009 | kabul edildi | [brief](tasks/T-011/brief.md) | metin (B-012 listesi) |
| T-011b | Mimari taslağının commit edilmesi (commit `667d96d`) | 2 | kayıtta yok | T-004 | kabul edildi | — | metin (B-012 listesi) |
| T-012 | Mimari taslağının bağımsız incelemesi | 2 | İnceleme agent'ı | T-004, T-011b | kabul edildi | [brief](tasks/T-012/brief.md) | metin (B-012 listesi); bulgular ARCHITECTURE rev.2'de |
| T-012b | Mimari düzeltmelerinin bağımsız doğrulaması | 2 | İnceleme agent'ı | T-012 | kabul edildi | — | metin (B-012 listesi); bulgular ARCHITECTURE rev.2'de (ör. Y8 → D-017, D-021) |
| T-013 | T-005 bulgularının düzeltilmesi (kayıtlar, `.gitignore`, AGENTS eklemeleri, D-014) | 2 | Dokümantasyon agent'ı | T-005 | kabul edildi | [brief](tasks/T-013/brief.md) | metin (B-012 listesi); commit `8a51f3c` |
| T-013b | `docs/ARCHITECTURE.md` rev.2'nin commit ve push edilmesi | 2 | kayıtta yok | T-004 | yapıldı — T-036 ile, sahip onayından sonra (commit `1f7c2dc`). İlk deneme izin sistemince reddedilmişti ("Modify Shared Resources", B-013). | — | Git geçmişi (`1f7c2dc`) |
| T-014 | Proje iskeleti + PII masker | 6 | Geliştirici agent'ı | — | kabul edildi | [brief](tasks/T-014/brief.md) | metin (B-012 listesi); commit `11694f5`; CI çalıştırması #1 başarılı ([TEST_REPORT](docs/TEST_REPORT.md)); soruları üzerine kararlar: [DECISIONS](docs/DECISIONS.md) D-036–D-038 |

## Uygulama dalgası (T-015…T-031)

Kaynak: [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §14 (rev.2, `1f7c2dc`). Tam kabul ölçütleri orada; aşağıdaki sütun yalnızca özettir. Her görev yalnızca kullandığı tabloların migration'ını getirir. Mock/sentetik veriyle yapılan işlerin sonuçları "sentetik" olarak raporlanır ([docs/TEST_REPORT.md](docs/TEST_REPORT.md)). CI numaraları ve run id'leri: TEST_REPORT.

**Bağımsız inceleme zorunlu** (geliştiren dışında bir agent): T-015 · T-018 + T-025 (birlikte) · T-019 + T-028 (birlikte) · T-027 · T-031.

| ID | Başlık | Aşama | Sahip (agent rolü) | Bağımlılık | Kabul ölçütleri (özet; tam metin ARCHITECTURE §14) | Bağımsız inceleme | Durum | Brief |
|---|---|---|---|---|---|---|---|---|
| T-015 | Çekirdek tablolar + kilitler + CAS | 6, 9 | Geliştirici agent'ı | T-014 | Temiz migration; Y1, Y2, Y5, Y6 testleri; `queued` tekilliği, koşullu draft INSERT, CAS yarışı, audit rolü UPDATE/DELETE yapamıyor. Fencing yöntemi testlerle seçilir (D-024). | zorunlu — T-033 yapıldı | kabul edildi — commit `747775e`, CI #4 başarılı; T-033 bulgularının düzeltmesi T-035'te | [brief](tasks/T-015/brief.md) |
| T-016 | T-010 kapsam genişletmesi (yalnızca belge) + mimari kabulü sonrası kayıt eşitlemesi | 3 | Dokümantasyon agent'ı | T-004 onayı | T-010 brief'i M1–M9 kalemlerini, ölçüm yöntemini ve çıktı biçimini içeriyor. | — | teslim edildi — Main Agent incelemesi bekliyor (commit `93d2ee5`, CI #2 başarılı) | [brief](tasks/T-016/brief.md) |
| T-017 | Avito gateway (okuma) + spec tabanlı mock | 3 | Geliştirici agent'ı | T-014 | Chats, chat detay, v3 messages; token (`expires_in`); öncelikli rate limiter (`live` > `bulk`); okuma hata sınıfları; mock kararlı ve kayan offset'le sayfalıyor. | — | kabul edildi — commit `57e2029`, CI #6 başarılı | [brief](tasks/T-017/brief.md) |
| T-018 | Gönderim istemcisi (yalnızca metin) | 7 | Geliştirici agent'ı | T-017 | Metin gönderimi; hata sınıflandırması; transport retry / retry middleware / redirect yok; her HTTP denemesi ayrı attempt; hata enjeksiyonu; otomatik yeniden deneme olmadığını kanıtlayan test. | zorunlu (T-025 ile) | sürüyor — dalda `c86b942` (CI #8 başarılı); ek görevler T-018b ve T-018c aşağıda | [brief](tasks/T-018/brief.md) |
| T-019 | Output filter (saf fonksiyon) | 6 | Geliştirici agent'ı | T-014 | ARCHITECTURE §7.2 kuralları (rakam/para, iletişim, ödeme, vaat, tamamlanma iddiası, ≤1000 karakter); girdi = son parçalar + olgu kağıdı; sahip düzeltmesi için uyarı modu. | zorunlu (T-028 ile); masker+filter incelemesi T-032 yapıldı | kabul edildi — commit `ecb73e0`, CI #3 başarılı; T-032 bulgularının düzeltmesi T-034'te | [brief](tasks/T-019/brief.md) |
| T-020 | History importer + ana anahtar yönetimi | 3 | — | T-015, T-017 | Mock üzerinde kesinti + devam, dedup, tombstone, yeniden listeleme farkı, şifreli ham depo, `attachment_unavailable`, rapor; ana anahtar yalnızca bellekte; canlı servis anahtarsız çalışıyor (D-034). | — | planlandı | — |
| T-021 | Ingest: webhook, poller, filigran, yazar sınıflandırması | 6 | — | T-015, T-017 | Webhook yalnızca chat_id/hash, p99 < 2 sn; 3 yoldan gelen aynı mesaj tek kayıt; tombstone; `activation_at` filigranı; yazar sınıfları ve `unknown` → pause. | — | planlandı | — |
| T-022 | Inventory port + sentetik adaptör + catalog/fitment | 5 | Geliştirici agent'ı | T-014 | Port arayüzü; etiketli sentetik W213 veri seti (`SYN-`, üretimde başlamıyor); `verified` yalnızca izinli kanıtla; sanal set; stok bağlantısı yokken `unknown`. | — | kabul edildi — commit `2e0e2d3`, CI #5 başarılı | [brief](tasks/T-022/brief.md) |
| T-022b | Fitment: doğrulanmış aralık dışındaki araç `incompatible` değil `needs_verification` (Main Agent'ın T-022 soru 1 kararı) | 5 | Geliştirici agent'ı | T-022 | `incompatible` yalnızca kabul edilen kanıtlı açık uyumsuzluk kaydıyla; `outside_verified_range` nedeni ve `owner_only_by_default`. | — | kabul edildi — commit `fb6c0ea`, CI #7 başarılı | — |
| T-023 | Conversation service + LLM orchestrator (fake provider) + `draft_only` | 6 | — | T-019, T-021, T-022 | Durum makinesi CAS; stale taslak; olgu kağıdı önceliği; sahip mesajı eşleştirme (D-017, D-021); LLM kesintisi davranışı. | — | planlandı | — |
| T-024 | Admin UI a: taslak listesi, "gönderdim", kill switch, sağlık | 6 | — | T-023 | Ayrı port 127.0.0.1/LAN; yalnızca güncel taslaklar; "gönderdim" akışı; kill switch grup kuralı; sağlık sayfası. | — | planlandı | — |
| T-025 | Outbox (metin; görseller kapalı) | 7, 9 | — | T-015, T-018 | Intent CAS; parça sırası; grup düzeyi kural; `unknown` → okuma → `sent`/`needs_owner` (D-015); 401/429 testi; `approve_to_send`'de eşleşmeyen kendi mesajı pause. | zorunlu (T-018 ile) | planlandı | — |
| T-026 | Teklif modeli | 7 | — | T-019, T-022 | `offer`/`offer_option`/`offer_line`; kodla toplam; seçenek ve teyit şablonları; `owner_modified`. | — | planlandı | — |
| T-027 | Yerel hold + teyit + sahip onayı + sipariş | 7, 9 | — | T-023, T-026 | Teyitsiz hold yok; `confirmation_id` UNIQUE; `held_local` sınırı; atomik çok satırlı hold; eşzamanlı son ürün testi (gerçek PostgreSQL); kanıtlı bırakma; ödeme ayrı (D-019). | zorunlu | planlandı | — |
| T-028 | Eval harness + KB sürümü | 8 (KB sürümü: 4) | — | T-019, T-023, T-026 | Çekirdek senaryolar; kapı kuralı; `kb_release` tamsayı; rollback kuralları değiştirmiyor (D-027). | zorunlu (T-019 ile) | planlandı | — |
| T-029 | Sağlık kontrolleri, uyarılar + Notifier portu | 9 | — | T-015, T-021 | `/healthz`, `/readyz`; uyarı tetikleyicileri; Notifier portu + test adaptörü (kanal BİLİNMİYOR, B-004). | — | planlandı | — |
| T-030 | Admin UI b: kalan ekranlar | 8 | — | T-024, T-027, T-028, T-029 | ARCHITECTURE §11 tablosunun geri kalanı. | — | planlandı | — |
| T-031 | Yedek, geri yükleme tatbikatı, aylık doğrulama, retention | 9 | — | T-020, T-025, T-027 | Boş makineye geri yükleme; §6.8 zorunlu testi; aylık otomatik doğrulama; kripto-silme ve tombstone testi; RUNBOOK girdisi. | zorunlu | planlandı | — |

## İncelemeler, düzeltmeler ve ek görevler (T-018b…T-040)

| ID | Başlık | Aşama | Sahip (agent rolü) | Bağımlılık | Durum | Brief | Teslim |
|---|---|---|---|---|---|---|---|
| T-018b | Gönderimde `ProxyError` → `unknown` (not_delivered değil) | 7 | Geliştirici agent'ı | T-018 | kayıtta yok — dalda commit `3a5f198` (CI #10 başarılı) | — | — |
| T-018c | Gönderim istemcisi output filter'ın `measure_part` ölçüsünü kullanır (≤1000 UTF-16 birimi ve ≤1000 UTF-8 bayt) | 7 | Geliştirici agent'ı | T-018, T-034 | kabul edildi — commit `afd6ad5`, CI #13 başarılı | — | Git geçmişi |
| T-032 | Masker (T-014) ve output filter (T-019) bağımsız güvenlik incelemesi | 6 | İnceleme agent'ı | T-014, T-019 | düzeltmelerle kabul edildi (düzeltme görevi: T-034) | [brief](tasks/T-032/brief.md) | metin (B-012 listesi) |
| T-033 | T-015 (çekirdek tablolar, kuyruk, kilitler, CAS) bağımsız incelemesi | 6, 9 | İnceleme agent'ı | T-015 | düzeltmelerle kabul edildi (düzeltme görevi: T-035) | [brief](tasks/T-033/brief.md) | metin (B-012 listesi) |
| T-034 | Masker + filter düzeltmeleri (T-032 bulguları) | 6 | Geliştirici agent'ı | T-032 | sürüyor — dalda commit `9bb67b7` var (CI #9 başarılı); teslim/kabul kararı kayıtta yok | [brief](tasks/T-034/brief.md) | — |
| T-035 | T-015 düzeltmeleri (T-033 bulguları) | 6, 9 | Geliştirici agent'ı | T-033 | kabul edildi — commit `15da795`, CI #11 başarılı; T-033b doğrulaması sürüyor | [brief](tasks/T-035/brief.md) | metin (B-012 listesi) |
| T-033b | T-035 düzeltmelerinin bağımsız doğrulaması | 6, 9 | İnceleme agent'ı | T-035 | sürüyor | — | — |
| T-036 | `docs/ARCHITECTURE.md` rev.2 commit'i (sahip onayı) + kayıt eşitlemesi | 2 | Dokümantasyon agent'ı | B-013 (sahip onayı 2026-09-27) | teslim edildi — Main Agent incelemesi bekliyor (ARCHITECTURE commit `1f7c2dc`; kayıt eşitlemesi ayrı commit) | [brief](tasks/T-036/brief.md) | metin |
| T-037 | Araştırma: Avito kurallarına uygun meşru alternatifler — doğrulanmış işletme profili istisnası, Avito'nun izin verdiği yerde web sitesi bağlantısı, Avito'nun kendi ödeme/teslimat hizmeti, aramayla web sitesine veya diğer kanallara gelen müşteriler ([DECISIONS](docs/DECISIONS.md) D-040) | 1 | Araştırma agent'ı | D-040 | kabul edildi | — | metin (B-012 listesi); özet: [docs/NOTES.md](docs/NOTES.md), [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §4 |
| T-038 | Web sitesi projesi için başlangıç (kickoff) dosyaları — ayrı proje, bu projenin kapsamı dışında ([DECISIONS](docs/DECISIONS.md) D-041) | — | kayıtta yok | D-041 | tamamlandı (Main Agent bildirimi) — commit'ler `60688d5`, `a49a565`; dalda ek commit'ler `51db517`, `d18799d`; dosyalar `website-kickoff/` | — | Git geçmişi |
| T-039 | Sahibin Windows bilgisayarında yerel kurulum: kurulum rehberi (`docs/SETUP_WINDOWS.md`), yerel gizli değer dosyası (Avito kimlik bilgileri için), salt okunur erişim kontrolü (mevcut tarifenin API'de neye izin verdiğini gösterir) | 1 | kayıtta yok | B-001, B-007, B-011 | sürüyor | — | — |
| T-040 | Avito desteğine ve poisk.vin'e (API erişimi) Rusça mektup taslakları, `docs/letters/`; mektupları sahip gönderir | 1 | kayıtta yok | D-040, B-015 | sürüyor | — | — |

Takip (görev kimliği henüz atanmadı): filtrenin nakit için `PAYMENT_TERMS_UNCONFIRMED` kuralının gevşetilmesi — [DECISIONS](docs/DECISIONS.md) D-039.

Gerçek erişim gerektirenler (sentetik/mock dışında): T-010 çalıştırması (B-007, B-009, B-011), gerçek inventory adaptörü (B-002), LLM sağlayıcısı (B-006), pilot (B-004).

## B-012 listesi — repoda olmayan teslim metinleri

Bu liste [BLOCKERS.md](BLOCKERS.md) B-012'nin **tek** listesidir; diğer kayıtlar "bkz. B-012" der. Metinler Main Agent'tadır (oturum scratchpad'indeki kopyalar geçicidir). Kabul edilen bulgular ilgili kayıtlara işlendi.

| Görev | Kabul edilen bulguların kalıcı yeri |
|---|---|
| T-001 | [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §2, [BLOCKERS.md](BLOCKERS.md) |
| T-002 | [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §3–§6, [docs/NOTES.md](docs/NOTES.md), [docs/DECISIONS.md](docs/DECISIONS.md) D-011–D-013, [BLOCKERS.md](BLOCKERS.md) |
| T-004 (ilk taslak, rev.1, rev.2) | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) rev.2 (`1f7c2dc`); kararlar [docs/DECISIONS.md](docs/DECISIONS.md) D-015–D-035 |
| T-005 | T-013 düzeltmeleri ([CHANGELOG.md](CHANGELOG.md) → T-013 kaydı) |
| T-009 | Git geçmişi (`9b4bdc1`) |
| T-011 | Git geçmişi (`fb13470`) |
| T-011b | Git geçmişi (`667d96d`) |
| T-012 | ARCHITECTURE rev.2 düzeltmeleri (`1f7c2dc`); kararlar [docs/DECISIONS.md](docs/DECISIONS.md) D-015–D-035 |
| T-012b | ARCHITECTURE rev.2 düzeltmeleri (`1f7c2dc`); Y8 → [docs/DECISIONS.md](docs/DECISIONS.md) D-017, D-021 |
| T-013 | Git geçmişi (`8a51f3c`) |
| T-014 | Git geçmişi (`11694f5`); [docs/DECISIONS.md](docs/DECISIONS.md) D-036–D-038; [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-015 | Git geçmişi (`747775e`); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-017 | Git geçmişi (`57e2029`); [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §7; [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) §6.10, §10.1 (M10); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-019 | Git geçmişi (`ecb73e0`); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-022 | Git geçmişi (`2e0e2d3`); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-022b | Git geçmişi (`fb6c0ea`); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-018c | Git geçmişi (`afd6ad5`); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-035 | Git geçmişi (`15da795`); [app/README.md](app/README.md); [docs/TEST_REPORT.md](docs/TEST_REPORT.md) |
| T-037 | [docs/NOTES.md](docs/NOTES.md) → "T-037 bulguları"; [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) §4; [docs/DECISIONS.md](docs/DECISIONS.md) D-039 (+%10 notu) |
| T-032 | T-034 düzeltmeleri ve regresyon testleri: `tests/test_filter_t032.py`, `tests/fixtures/filter/t032_cases.json` (commit `9bb67b7`; T-034 kabulü bekleniyor) |
| T-033 | T-035 düzeltmeleri (commit `15da795`) |

Her yeni metin teslimi kabul edildiğinde bu listeye eklenir.
