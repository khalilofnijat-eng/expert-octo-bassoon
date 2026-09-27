# CHANGELOG — Önemli değişiklikler

En yeni kayıt en üstte. Her kayıt, değişikliği içeren commit'in kısa hash'ini taşır; kaydı içeren commit'in kendi hash'i bir sonraki kayıt güncellemesinde eklenir.

## 2026-09-27 (T-013) — commit: bir sonraki güncellemede eklenecek

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
