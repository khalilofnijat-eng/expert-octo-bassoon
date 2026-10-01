# CHANGELOG — Önemli değişiklikler

En yeni kayıt en üstte. Her kayıt, değişikliği içeren commit'in kısa hash'ini taşır; kaydı içeren commit'in kendi hash'i bir sonraki kayıt güncellemesinde eklenir.

## 2026-10-01 (T-042 + T-044, bulut aşamasının son devri) — commit: bu kaydı içeren commit (hash'i TASKS/HANDOFF güncellemesinde eklenecek)

- Yeni: [LOCAL_SESSION_PROMPT.md](LOCAL_SESSION_PROMPT.md) (yerel oturuma ilk mesaj), [docs/VAULT_PLACEMENT.md](docs/VAULT_PLACEMENT.md) (kasaya yerleştirme, `UV_PROJECT_ENVIRONMENT`); README'ye "Buradan başla" kutusu.
- TASKS: T-039/T-039b (`1ee147b`, `cd0def9`), T-040b (`c358f4e`), T-041 (`6d013f8`), T-043 (`7cb06d9`) kabul; T-033b yarıda kaldı, yerel oturumda yeniden; yeni T-044, T-045 (T-041 doğrulaması); sıradaki kimlik T-046.
- DECISIONS: D-044 uygulandı (T-041). BLOCKERS: B-009'a yerel oturum notu. LESSONS_LEARNED: kullanım sınırı → küçük görev, yeşil ara adımları commit et.
- `.env.example`: `AVITO_USER_ID`, yorumlu `ASSISTANT_SECRETS_FILE`. `docs/SETUP_WINDOWS.md`: kasaya yerleştirmeyle uyum. `scripts/README.md`, `tests/README.md` güncellendi. STATE, HANDOFF, oturum kaydı: bulut aşamasının son durumu.

## 2026-09-27 (T-042) — aynı commit

- BLOCKERS: sahip cevapları aynen alıntıyla kaydedildi — B-001 (Windows, "khalilofnijat" Chrome profili; T-039), B-007 (Pro, Базовый'da API yok, «Расширенный»'e geçiş; spec kopyası «Максимальный» diyor, canlı doğrulanacak), B-011 (yerel gizli değer dosyası), B-002 kısmen çözüldü (Vault), B-004 kısmen çözüldü (sahibin Windows bilgisayarı), B-003 (kurulumda bulunacak), B-010 (beklemede). "Tekrar sorulmasın" notu — [BLOCKERS.md](BLOCKERS.md). AGENTS §6: cevaplanan sorular yeniden sorulmaz.
- DECISIONS: D-043 (T-034 filtre kararları D-a…D-l; D-l değiştirildi), D-044 (T-041 filtre kararları), D-045 (pilot barındırma), D-046 (Vault envanter kaynağı); D-039 takibi T-041'e bağlandı — [docs/DECISIONS.md](docs/DECISIONS.md).
- TASKS: T-016, T-018, T-018b, T-036, T-038, T-040 kabul; T-034, T-032b düzeltmelerle kabul; yeni T-040b, T-041, T-042, T-043; T-039 ve T-040 sahipleri; sıradaki kimlik T-044 — [TASKS.md](TASKS.md).
- `app/README.md`: mimari kabul edildi, modül listesi, `APP_ENV`; DB rol adımları [docs/RUNBOOK.md](docs/RUNBOOK.md) → "Veritabanı rolleri"ne taşındı. `.env.example`: `AUTOMATION_MODE` yorumundan `auto_scoped` çıkarıldı. ARCHITECTURE §16 durum satırı. STATE, HANDOFF, oturum kaydı.

## 2026-09-27 (T-036, kayıt eşitlemesi) — commit `030bd6e`

- TASKS: T-004 commit edildi, T-013b yapıldı; T-015, T-017, T-019, T-022, T-022b, T-018c, T-035, T-037 kabul; T-032, T-033 düzeltmelerle kabul; T-016 ve T-036 teslim edildi; T-018, T-034, T-033b, T-039, T-040 sürüyor; T-018b, T-038 eklendi; B-012 listesi genişletildi — [TASKS.md](TASKS.md).
- BLOCKERS: B-013 çözüldü; B-005 kısmen çözüldü (ödeme yöntemleri, ИП, Avito Доставка); B-002, B-004 yeniden soruldu; yeni B-015 (poisk.vin API) — [BLOCKERS.md](BLOCKERS.md).
- DECISIONS: D-039 (ödeme yöntemleri; +%10 yalnızca B2B), D-040 (Avito moderasyonu atlatılmaz), D-041 (web sitesi ayrı proje), D-042 (Messenger API tarifesi için üç seçenek) — [docs/DECISIONS.md](docs/DECISIONS.md).
- INTEGRATIONS: M10/M11 ve T-037 belirsizlikleri, uygulanan gateway bölümü (§7). NOTES: sahip cevapları ve T-037 bulguları. T-010 brief'ine M10, M11 ve gateway kullanım notları. `tests/README.md`: yeni test paketleri ve DB testleri. `.env.example`: `APP_ENV`. Brief'ler: T-017, T-018, T-022, T-032–T-036. STATE, HANDOFF, PLAN, oturum kaydı, TEST_REPORT güncellendi.

## 2026-09-27 (T-036, mimari) — commit `1f7c2dc`

- Mimari rev.2 sahip onayıyla commit edildi (B-013). Küçük düzeltmeler: başlık "KABUL EDİLDİ"; §6.10 uç nokta başına token bucket (T-017); §10.1 M10 ve M11; §7.4 `[TYPE_n]` — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 2026-09-27 — kabul edilen uygulama commit'leri

- T-019 output filter `ecb73e0`; T-015 çekirdek DB/kuyruk/kilitler/CAS `747775e`; T-022 inventory + catalog/fitment `2e0e2d3`; T-017 Avito okuma istemcisi + mock `57e2029`; T-022b fitment kuralı `fb6c0ea`; T-018c gönderim istemcisinde ortak `measure_part` `afd6ad5`; T-035 T-015 düzeltmeleri `15da795`. CI sonuçları: [docs/TEST_REPORT.md](docs/TEST_REPORT.md). Kabulü kayıtta olmayan commit'ler (T-018 `c86b942`, T-018b `3a5f198`, T-034 `9bb67b7`) ve web sitesi başlangıç dosyaları (T-038) için: [TASKS.md](TASKS.md).

## 2026-09-27 (T-016) — commit `93d2ee5`

- Mimari rev.2 kabulü kayda geçti; `docs/ARCHITECTURE.md` rev.2'nin commit'i sahip iznini bekliyor (yeni engel B-013). Mimari kararları D-015–D-035, T-014 soruları üzerine kararlar D-036–D-038 — [docs/DECISIONS.md](docs/DECISIONS.md).
- T-004 (rev.2), T-012, T-012b, T-013, T-014 kabul edildi; T-013b engelli; uygulama dalgası T-015…T-031 bağımlılık, kabul özeti ve zorunlu bağımsız incelemelerle eklendi; B-012 listesi genişletildi — [TASKS.md](TASKS.md).
- T-010 kapsamı: GET-only ölçüm betiği, M1–M9 ve okundu yan etkisinin canlı doğrulaması, çıktı biçimi, kabul ölçütleri, güvenlik kontrol listesi — [tasks/T-010/brief.md](tasks/T-010/brief.md).
- BLOCKERS: B-013, B-014 ve B-002/B-004/B-005/B-006'ya sahibe sorulan ek sorular.
- Brief'ler: T-012, T-013, T-014, T-015, T-016, T-019. `.gitignore`: araç önbellekleri ve kapsam çıktıları. `knowledge/README.md`: KB'nin doğruluk kaynağı DB (D-028). PLAN'a aşama–görev eşlemesi; TEST_REPORT'a T-014 sentetik testleri; STATE, HANDOFF, oturum kaydı güncellendi.

## 2026-09-27 (T-014) — commit `11694f5`

- Python proje iskeleti (uv, FastAPI, ayarlar, `/healthz`), PII maskeleyici, sentetik birim testleri ve CI — [app/README.md](app/README.md), [tests/README.md](tests/README.md). CI çalıştırması #1 başarılı ([docs/TEST_REPORT.md](docs/TEST_REPORT.md)).

## 2026-09-27 (T-013) — commit `8a51f3c`

- Bağımsız inceleme (T-005) bulguları düzeltildi.
- STATE, HANDOFF ve oturum kaydı görev durumlarını tekrar etmeyecek biçimde yeniden yazıldı; durumların tek kaynağı [TASKS.md](TASKS.md).
- T-001 kanıt özeti ve Avito uç nokta tablosu kalıcı kayda geçti; DECISIONS gerekçeleri depo içi bölümlere bağlandı — [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md), [docs/DECISIONS.md](docs/DECISIONS.md).
- Güven etiketi tüm kayıtlarda "resmî spec'in topluluk kopyası — resmî kaynakla karşılaştırılmadı, canlı doğrulanmadı" oldu.
- `.gitignore` genişletildi: `.env.*`, görseller, çerez/oturum dosyaları, dökümler/yedekler, kimlik dosyaları, `.jsonl`/`.csv` (sentetik `tests/fixtures/` istisnasıyla).
- BLOCKERS'a "Sahibe soruldu" sütunu ve müdahale kaynağı etiketi eklendi; B-012 listesi yalnızca TASKS'ta.
- AGENTS: rol tablosuna Dokümantasyon ve İnceleme agent'ları, kabul sonrası güncelleme listesi, B-008'e kadar işletme bilgisi commit yasağı, yasak Avito çağrıları, sahip kuralları, denetim kaydı yeri ve UTC.
- Yeni karar D-014 (geliştirme dalı); T-012 ve T-013 eklendi; T-006 ve PLAN bağımlılıkları D-011'e uyarlandı; tekrarlanan olgular bağlantıyla değiştirildi.

## 2026-09-27 (T-011b) — commit `667d96d`

- Mimari taslağı (T-004 çıktısı) eklendi — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## 2026-09-27 (T-011) — commit `fb13470`

- Görev teslim kuralı B-012'ye uyarlandı: teslim raporu Main Agent'a metin olarak, şablon yapısında verilir; sahip kararına kadar diske yazılmaz — [AGENTS.md](AGENTS.md) §3, [tasks/README.md](tasks/README.md), şablonlar, T-001/T-002 brief'leri.
- T-010 bağımlılığına B-009 eklendi; T-009 kabul edildi; T-011 eklendi — [TASKS.md](TASKS.md).
- GitHub varsayılan dalı doğrulandı ve kaydedildi — [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md).

## 2026-09-27 (T-009) — commit `9b4bdc1`

- T-001 ve T-002 bulguları ortak kayıtlara işlendi: [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md), [docs/NOTES.md](docs/NOTES.md), [BLOCKERS.md](BLOCKERS.md).
- Yeni kararlar: D-011 (üretim kanalı resmî Messenger API), D-012 (salt okunur derinlik ölçümüyle başlama), D-013 (kendi ince API istemcisi) — [docs/DECISIONS.md](docs/DECISIONS.md).
- Yeni engeller: B-009 (avito.ru ağ engeli), B-010 (152-FZ), B-011 (Avito API kimlik bilgileri), B-012 (rapor dosyası yazma kısıtı). B-001, B-007, B-008 güncellendi.
- Yeni görevler: T-009, T-010. T-004, T-005 ve T-009 için brief'ler eklendi — [TASKS.md](TASKS.md).
- İlk ders kaydı: [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md).

## 2026-09-27 (T-003) — commit `dc7fd1a`

- Kalıcı kayıt düzeni iskeleti oluşturuldu: kök kayıtlar, `docs/`, `sessions/`, `tasks/`, klasör README'leri ve `.gitignore`. Dosya düzeni kararı: [docs/DECISIONS.md](docs/DECISIONS.md) D-003.
- Sahibin ilk talimatı değiştirilmez kopya olarak kaydedildi: [docs/OWNER_REQUEST_2026-09-27.md](docs/OWNER_REQUEST_2026-09-27.md).
