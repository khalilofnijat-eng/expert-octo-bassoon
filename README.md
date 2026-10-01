# Avito Müşteri Asistanı — Başlangıç Sayfası

Bu depo, Avito'da otomotiv parçası satan işletme için kurulacak müşteri asistanının proje klasörüdür (ileride Obsidian Vault içindeki `Avito-Assistant/` klasörü olacak; bkz. [BLOCKERS.md](BLOCKERS.md) B-003). Asistan; müşteri mesajını ve ilanı anlayacak, depodaki gerçek ürün/stok/fiyat/fotoğraf bilgisini kullanacak ve konuşmayı işletmenin kuralları içinde siparişe taşıyacak. Güncel durum için: **[STATE.md](STATE.md)**.

> [!tip] Buradan başla (sahip, Windows bilgisayarı)
> 1. Klasörü kasaya yerleştir: [docs/VAULT_PLACEMENT.md](docs/VAULT_PLACEMENT.md)
> 2. Kurulum, Avito kimlik bilgileri ve erişim kontrolü: [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md)
> 3. Yerel Claude oturumuna ilk mesaj: [LOCAL_SESSION_PROMPT.md](LOCAL_SESSION_PROMPT.md)

## Yeni oturum

Önce [AGENTS.md](AGENTS.md)'yi oku; oturum başı okuma sırası orada (§1).

## Tüm kayıtlar

| Kayıt | İçerik |
|---|---|
| [AGENTS.md](AGENTS.md) | Ortak agent kuralları, görev dağıtımı, çalışma yöntemi |
| [CLAUDE.md](CLAUDE.md) | Claude Code giriş talimatı |
| [STATE.md](STATE.md) | Mevcut gerçek durum (tek kaynak) |
| [HANDOFF.md](HANDOFF.md) | Yeni oturum için devam özeti |
| [TASKS.md](TASKS.md) | Görevler, sahipleri, durumları (tek kaynak) |
| [BLOCKERS.md](BLOCKERS.md) | Engeller (tek kaynak) |
| [CHANGELOG.md](CHANGELOG.md) | Önemli değişiklikler |
| [docs/OWNER_REQUEST_2026-09-27.md](docs/OWNER_REQUEST_2026-09-27.md) | Sahibin ilk talimatı (değiştirilmez) |
| [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md) | Hedef, kapsam, başarı ölçütleri |
| [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) | Mimari ve veri akışları (durumu: [STATE.md](STATE.md)) |
| [docs/PLAN.md](docs/PLAN.md) | Aşamalar ve bağımlılıklar |
| [docs/DECISIONS.md](docs/DECISIONS.md) | Kararlar ve verilen canlı yetkiler (tek kaynak) |
| [docs/NOTES.md](docs/NOTES.md) | İşletme ve uygulama notları |
| [docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md) | Hatalar, kök nedenler, önlemler |
| [docs/INTEGRATIONS.md](docs/INTEGRATIONS.md) | Bağlantılar ve doğrulanmış yetenekler |
| [docs/TEST_REPORT.md](docs/TEST_REPORT.md) | Çalıştırılan testler (sentetik / gerçek ayrı) |
| [docs/RUNBOOK.md](docs/RUNBOOK.md) | Başlatma, durdurma, yedekleme, arıza giderme |
| [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) | Windows kurulumu, Avito kimlik bilgileri, erişim kontrolü |
| [docs/VAULT_PLACEMENT.md](docs/VAULT_PLACEMENT.md) | Proje klasörünü Obsidian kasasına yerleştirme |
| [docs/VAULT_SURVEY.md](docs/VAULT_SURVEY.md) | Kasanın salt okunur yapı taraması |
| [LOCAL_SESSION_PROMPT.md](LOCAL_SESSION_PROMPT.md) | Yerel oturuma ilk mesaj |
| [sessions/README.md](sessions/README.md) | Oturum özetleri |
| [tasks/README.md](tasks/README.md) | Alt agent görev kayıtları ve teslimleri |

## Klasör haritası

| Klasör | Amaç |
|---|---|
| kök | Oturum başında okunan ortak kayıtlar |
| `docs/` (giriş: [docs/PROJECT_BRIEF.md](docs/PROJECT_BRIEF.md)) | Referans belgeler (talep, özet, mimari, plan, kararlar, notlar, entegrasyon, test, runbook) |
| [sessions/](sessions/README.md) | Oturum özetleri |
| [tasks/](tasks/README.md) | Görev brief'leri ve teslim raporları |
| [knowledge/](knowledge/README.md) | Bilgi tabanının PII içermeyen dökümleri (doğruluk kaynağı DB) |
| [operations/](operations/README.md) | İşletim yapılandırma şablonları, izleme ve denetim politikaları |
| [app/](app/README.md) | Uygulama kodu |
| [tests/](tests/README.md) | Testler ve sabit değerlendirme senaryoları |
| [scripts/](scripts/README.md) | Yardımcı betikler |
| [data/](data/README.md) | Yalnızca README Git'te; canlı veri Git ve Vault dışında |
