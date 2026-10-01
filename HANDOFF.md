# HANDOFF — Yeni oturum için devam özeti

**Son güncelleme:** 2026-10-01 (T-044, bulut aşamasının sonu)

Okuma sırası ve kurallar: [AGENTS.md](AGENTS.md) §1. Mevcut durum: [STATE.md](STATE.md). Görev durumları ve bağımlılıklar yalnızca [TASKS.md](TASKS.md)'de; engeller ve sahip cevapları yalnızca [BLOCKERS.md](BLOCKERS.md)'de.

## Nerede kaldık

**Bulut aşaması bitti.** Sahip proje klasörünü Obsidian kasasına koyar ([docs/VAULT_PLACEMENT.md](docs/VAULT_PLACEMENT.md)) ve kendi Windows bilgisayarında yerel oturum açıp [LOCAL_SESSION_PROMPT.md](LOCAL_SESSION_PROMPT.md)'yi ilk mesaj olarak yapıştırır.

Mimari rev.2 kabul edildi (`1f7c2dc`). Kabul edilen uygulama ve araç görevleri: T-014–T-019, T-022, T-022b, T-035, T-039/T-039b (Windows kurulumu, erişim kontrolü), T-041 (filtre düzeltmeleri, D-044), T-043 (Vault taraması); T-034 ve T-032b düzeltmelerle kabul. Belgeler: T-036, T-038, T-040/T-040b (mektuplar). Hepsi yalnızca sentetik veriyle test edildi ([docs/TEST_REPORT.md](docs/TEST_REPORT.md)). Dış sistem bağlantısı yok; sahip kurulum betiklerini henüz çalıştırmadı.

Sahip cevapları (aynen alıntılar [BLOCKERS.md](BLOCKERS.md)'de): Avito hesabı Windows bilgisayarındaki "khalilofnijat" Chrome profilinde (B-001); Pro profili, Базовый'da API yok, «Расширенный»'e geçecek (B-007 — spec kopyası «Максимальный» diyor, canlı doğrulanacak); kimlik bilgileri yerel dosyaya (B-011); stok, fiyat ve fotoğraflar Obsidian Vault'ta (B-002, D-046); pilot kendi bilgisayarında (B-004, D-045). Sahip hesap türü, tarife ve erişimin **tekrar sorulmamasını** istedi ([AGENTS.md](AGENTS.md) §6).

## Sıradaki eylemler (yerel oturum)

0. **Ortamı doğrula:** git, uv, Python 3.11, PostgreSQL 16 (Windows kurulum planı, sahip onayıyla), klasör bir clone mu ve `claude/youthful-goldberg-l427nm` dalına push yetkisi var mı; `UV_PROJECT_ENVIRONMENT` kasa dışında mı.
1. **Avito erişimi:** sahibi [docs/SETUP_WINDOWS.md](docs/SETUP_WINDOWS.md) boyunca yönlendir; erişim kontrolünün sonucunu yorumla (B-007, D-042). Kasa yolu bu kurulumda bulunur (B-003).
2. **Vault:** `scripts/vault_survey.py` salt okunur ([docs/VAULT_SURVEY.md](docs/VAULT_SURVEY.md)); rapordaki `Avito-Assistant` alt ağacını yok say; sonra salt okunur Vault adaptörü (T-007, D-046). Vault izinsiz değiştirilmez.
3. **Bağımsız incelemeler:** T-033b yeniden, T-045 (T-041).
4. **T-010** salt okunur ölçüm (çalışan Messenger API gerekir).
5. **Sentetik konuşma akışı:** T-020, T-021, T-023; sonra T-024. T-025 de başlayabilir (T-015, T-018 kabul).
6. **Windows servisleri** ve yalnızca poller modu (D-045).
7. **Kalan sahip cevapları:** B-005'in kalanı, B-008, B-012, uyarı kanalı (B-004), fitment kaynağı ve set yapısı (B-002). Sahibin bekleyen işleri: mektuplar, depoyu özel yapmak, +%10 muhasebeci teyidi, tarife değişikliği.

## Uyarılar

- Önceki agent'ların veya arka plan süreçlerinin hâlâ çalıştığını varsayma; sürmekte görünen görevlerin gerçek durumunu kontrol et.
- Push edilmemiş iş kaybolabilir; kullanım sınırları oturumu kesebilir: görevleri küçük tut, her yeşil ara adımı commit ve push et ([docs/LESSONS_LEARNED.md](docs/LESSONS_LEARNED.md)).
- Aynı çalışma ağacında birden fazla agent commit ediyor: yalnızca açık yollarla stage; ortak dosya başka agent'ın işiyle kirliyse ayrı index (`GIT_INDEX_FILE`) kullan. `.git/index.lock` silinmez.
- Alt agent'lar rapor dosyası yazamaz; brief'lerde rapor dosyası isteme, teslimi metin olarak al (bkz. B-012).
- B-008 çözülene kadar işletmeye özgü bilgi commit edilmez ([AGENTS.md](AGENTS.md) §5); istisna: müşteriye açık ödeme yöntemleri (D-039). Vault içeriği de bu kapsamdadır: T-043 çıktısı anonimleştirilmiş olmalıdır.
- Kodda harfli karar kimlikleri (`app/safety/`: "D-a" … "D-l") [docs/DECISIONS.md](docs/DECISIONS.md) D-043'te; T-041 kararları D-044'te.
