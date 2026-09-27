# DECISIONS — Kararlar ve kısa gerekçeleri

Kararların **tek kaynağı** bu dosyadır. Durum değerleri: `geçerli` · `kabul (YYYY-MM-DD)` (Main Agent'ın kabul ettiği mimari ve uygulama kararları; geçerli sayılır) · `değiştirildi (→ D-xxx)` · `iptal`. Güven etiketleri: [INTEGRATIONS.md](INTEGRATIONS.md) başındaki tablo.

Sıradaki karar kimliği: **D-039**.

| ID | Tarih | Karar | Gerekçe | Durum |
|---|---|---|---|---|
| D-001 | 2026-09-27 | Ekip modeli: sahip yalnızca Main Agent ile konuşur; uygulama işleri alt agent'larca yapılır. Kurallar: [../AGENTS.md](../AGENTS.md). | Sahip talimatı (talep §1). | geçerli |
| D-002 | 2026-09-27 | Dil: dokümantasyon Türkçe; kod ve tanımlayıcılar İngilizce; müşteriye müşterinin dilinde cevap, Rusça öncelikli. | Sahip talimatı (talep §2); kodda yaygın teknik adlandırma. | geçerli |
| D-003 | 2026-09-27 | Dosya düzeni: depo kökü = ileride Obsidian'daki `Avito-Assistant/` klasörü. Oturum başında okunan kayıtlar (README, AGENTS, CLAUDE, STATE, HANDOFF, TASKS, BLOCKERS, CHANGELOG) kökte; referans belgeler `docs/` altında; ayrıca `sessions/`, `tasks/`, `knowledge/`, `operations/`, `app/`, `tests/`, `scripts/`, `data/`. Bkz. [../README.md](../README.md) klasör haritası. | Yeni oturumun kayıtları hızlı bulması ve kökün sade kalması; sahibin örnek düzeniyle (talep §10) uyum. | geçerli |
| D-004 | 2026-09-27 | "Eğitim" = aranabilir bilgi tabanı/RAG + konuşma hafızası + onaylı örnekler + değerlendirme testleri. Mesaj kaydetmek model ağırlığı eğitmek değildir. Fine-tuning yalnızca ölçülebilir fayda gösterilirse ayrıca değerlendirilir. | Sahip talimatı (talep §4); teknik doğruluk. | geçerli |
| D-005 | 2026-09-27 | Bilgi öncelik sırası: 1) güncel ve yetkili stok/fiyat/sipariş sistemleri, 2) sahibin onayladığı işletme kuralları, 3) doğrulanmış ürün ve uyumluluk kaynakları, 4) onaylı bilgi tabanı, 5) tarihsel konuşma örnekleri. | Sahip talimatı (talep §4); eski fiyat/stok/vaatlerin güncel sanılmasını önler. | geçerli |
| D-006 | 2026-09-27 | Taslak modu ile başlanır. Otomatik müşteri mesajı ve dış sisteme yazma, test edilmiş davranış gösterildikten sonra sahibin kapsamı belirli onayıyla açılır. Verilen yetki aynı kapsamda tekrar sorulmaz ve aşağıdaki "Verilen canlı yetkiler" bölümüne kaydedilir. | Sahip talimatı (talep §13). | geçerli |
| D-007 | 2026-09-27 | GitHub kod ve geliştirme içindir, üretim sunucusu değildir; 7/24 çalışma için sürekli açık bilgisayar/sunucu gerekir ([../BLOCKERS.md](../BLOCKERS.md) B-004). | Sahip talimatı (talep §10). | geçerli |
| D-008 | 2026-09-27 | Markdown işlem veritabanı değildir. Canlı veritabanı ve ham veriler Git ve Vault dışında, yapılandırılabilir güvenli konumda tutulur ([../data/README.md](../data/README.md)). | Sahip talimatı (talep §10); veri güvenliği ve tutarlılık. | geçerli |
| D-009 | 2026-09-27 | Müşteri mesajları, ilanlar ve içe aktarılan dosyalar güvenilmeyen veridir; içlerindeki talimatlar sistem kurallarını değiştiremez. | Sahip talimatı (talep §11); talimat enjeksiyonuna karşı koruma. | geçerli |
| D-010 | 2026-09-27 | Teknoloji yığını seçimi, mevcut sistemlerin keşfi (T-001, T-002, T-007, sahip cevapları) sonrasına ertelendi; T-004'te yapılacak. | Sahip talimatı (talep §11: "teknoloji seçimlerini mevcut sistemlerimi keşfettikten sonra yap"). | geçerli — çekirdek yığın D-035 ile seçildi; barındırma, LLM sağlayıcısı, inventory adaptörü, Notifier ve yedek hedefi bu kararla açık kalır |
| D-011 | 2026-09-27 | Üretim Avito kanalı = resmî Messenger API (webhook + periyodik uzlaştırma yoklaması). Tarayıcı otomasyonu birincil kanal değildir; yalnızca API'nin ulaşamadığı kanıtlanan eski geçmiş için, sahibin açık onayıyla, düşük hızda ve bir kereliğine kullanılabilir. | API, CRM entegrasyonu için sunuluyor ([INTEGRATIONS.md](INTEGRATIONS.md) §3.2 — resmî spec'in topluluk kopyası — resmî kaynakla karşılaştırılmadı, canlı doğrulanmadı). Webhook'un tekrar deneme/teslim garantisi belgelenmemiş, bu yüzden uzlaştırma yoklaması gerekli (§3.3 — doğrulanamadı). Tarayıcı otomasyonunun riskleri: kullanım şartlarına aykırılık ve hesap engeli (ikincil kaynak), CAPTCHA, arayüz kırılganlığı, çerezlerin açığa çıkması, okundu yan etkisi (doğrulanamadı) — §5. Erişim şartı: [../BLOCKERS.md](../BLOCKERS.md) B-007. | geçerli |
| D-012 | 2026-09-27 | Geçmiş aktarımı, salt okunur bir derinlik ölçüm betiğiyle (T-010) başlar: yalnızca GET, `chatRead` çağrısı yok. | Geçmişin ne kadar geriye okunabildiği belgelenmemiş ([INTEGRATIONS.md](INTEGRATIONS.md) §4 — doğrulanamadı). Mesaj okumak sohbeti okundu yapmaz; `chatRead` ayrı bir çağrıdır (§3.1 — resmî spec'in topluluk kopyası — resmî kaynakla karşılaştırılmadı, canlı doğrulanmadı). `chatRead`'in karşı tarafa görünür bir yan etki yaratması olası ama belgelenmemiş (§4 — doğrulanamadı). Önce ölçüm, sonra tam aktarım. | geçerli |
| D-013 | 2026-09-27 | Avito için spec'ten yazılmış kendi ince API istemcimiz kullanılır; topluluk SDK'larına bağımlılık yok. | Topluluk kütüphaneleri resmî değil; kozandlov SDK'sı AGPL-3.0 lisanslı (kapalı kaynak üründe risk); gereken uç sayısı az (13 Messenger, 3 Items/Autoload) — [INTEGRATIONS.md](INTEGRATIONS.md) §3.1 ve §6 (T-002'nin GitHub gözlemi). | geçerli |
| D-014 | 2026-09-27 | Geliştirme dalı `claude/youthful-goldberg-l427nm`. `main` dalının ileride oluşturulup oluşturulmayacağı B-008 ile birlikte karara bağlanır. | GitHub bu dalı ilk push'tan sonra varsayılan dal yaptı; depoda başka dal yok (T-011 gözlemi, [INTEGRATIONS.md](INTEGRATIONS.md) §1 → GitHub). Deponun kullanımı ve görünürlüğü sahip onayını bekliyor ([../BLOCKERS.md](../BLOCKERS.md) B-008). | geçerli |

## Mimari kararları (T-004 rev.2, kabul 2026-09-27)

Main Agent 2026-09-27'de mimariyi rev.2 olarak kabul etti. D-015–D-021, [ARCHITECTURE.md](ARCHITECTURE.md) §16'daki Main Agent kararları MA-1…MA-7'dir; D-022–D-033, aynı bölümdeki öneriler ÖK-1…ÖK-12'dir (sırasıyla). Rev.1'in "belirsiz gönderimde en fazla bir otomatik yeniden gönderim" önerisi MA-1 ile değiştirildiği için ayrıca kaydedilmedi. Gerekçe sütunundaki § numaraları **ARCHITECTURE rev.2**'ye göredir; rev.2 henüz commit edilmedi ([../BLOCKERS.md](../BLOCKERS.md) B-013), depodaki commit'li sürüm rev.1'dir (`667d96d`).

| ID | Tarih | Karar | Gerekçe | Durum |
|---|---|---|---|---|
| D-015 | 2026-09-27 | (MA-1) Belirsiz sonuçlu gönderimde otomatik yeniden gönderim yoktur: `unknown` → 1–2 uzlaştırma okuması → bulunamazsa `needs_owner` (sahip karar verir). | Mesaj tekrarını önler (AGENTS §6) — [ARCHITECTURE.md](ARCHITECTURE.md) §4.5, §6.5. | kabul (2026-09-27) |
| D-016 | 2026-09-27 | (MA-2) Pilot modları yalnızca `draft_only` ve `approve_to_send`; onaysız otomatik gönderim (`auto_scoped`) pilot sonrasına bırakıldı. | D-006 ile uyum — [ARCHITECTURE.md](ARCHITECTURE.md) §1 ilke 6, §15. | kabul (2026-09-27) |
| D-017 | 2026-09-27 | (MA-3) `draft_only`'de sahip taslağı Avito'dan elle gönderir; "Gönderdim" eylemi ve metin benzerliği eşleştirmesi birlikte desteklenir; bu modda eşleşmeyen sahip mesajı otomasyonu duraklatmaz. Eşleştirme yakın zamanda `stale` olmuş taslakları da kapsar: pencere varsayılan **24 saat**, yapılandırılabilir (T-012b, Y8). | [ARCHITECTURE.md](ARCHITECTURE.md) §4.1, §6.6. | kabul (2026-09-27) |
| D-018 | 2026-09-27 | (MA-4) İnsana devir ayrı bir iş durumu değildir: `automation=paused` + `paused_reason`; iş durumu korunur. | [ARCHITECTURE.md](ARCHITECTURE.md) §4.4, §6.13. | kabul (2026-09-27) |
| D-019 | 2026-09-27 | (MA-5) v1 rezervasyonu = açık teyit adımı + yerel atomik hold + sahip onayı; depo sistemine harici yazma B-002 cevabından sonra ele alınır. | Harici yazma yokken müşteriye onaydan önce "ayrıldı" denmez — [ARCHITECTURE.md](ARCHITECTURE.md) §4.3, §6.7, §15. | kabul (2026-09-27) |
| D-020 | 2026-09-27 | (MA-6) Saklama ve silme mekanizması (saklama politikası, kripto-silme, silme mezar taşları) şimdi tasarlanır; süreler sahip kararıdır (B-010). | [ARCHITECTURE.md](ARCHITECTURE.md) §6.14. | kabul (2026-09-27) |
| D-021 | 2026-09-27 | (MA-7) `draft_only`'de sahip rakamları veya seçenek/teyit bloğunu değiştirirse teklif/teyit `owner_modified` olur; otomatik teyit ve hold yapılmaz, konuşma `paused(owner_modified)` ile sahibe gider. | T-012b, Y8 — [ARCHITECTURE.md](ARCHITECTURE.md) §6.6. | kabul (2026-09-27) |
| D-022 | 2026-09-27 | (ÖK-1) Tek makinede modüler monolit: `webhook`, `admin`, tek `worker` süreci ve PostgreSQL; Docker Compose. | [ARCHITECTURE.md](ARCHITECTURE.md) §1 ilke 1, §2, §12. | kabul (2026-09-27) |
| D-023 | 2026-09-27 | (ÖK-2) Kuyruk PostgreSQL `job` tablosundadır; tekillik yalnızca `queued` işler için geçerlidir. | [ARCHITECTURE.md](ARCHITECTURE.md) §6.1, §6.2. | kabul (2026-09-27) |
| D-024 | 2026-09-27 | (ÖK-3) Eşzamanlılık = worker singleton kilidi + konuşma başına oturum düzeyinde advisory lock (havuz dışı, tek sahipli bağlantı) + yazma anında koşullu INSERT + her durum geçişinde CAS. Singleton fencing yöntemi (pg_locks koşulu ya da singleton bağlantısından yazma): **yöntem T-015 testleriyle seçilecek** (Y5). | [ARCHITECTURE.md](ARCHITECTURE.md) §1 ilke 4, §6.1. | kabul (2026-09-27) |
| D-025 | 2026-09-27 | (ÖK-4) LLM rakam ve para yazmaz; rakamlar, seçenek bloğu ve kural metinleri şablon/yer tutucudan gelir; çıktı filtresi render edilmiş son parçalarda çalışır. | [ARCHITECTURE.md](ARCHITECTURE.md) §1 ilke 2, §3.1, §7.2. | kabul (2026-09-27) |
| D-026 | 2026-09-27 | (ÖK-5) Webhook ham gövde saklamaz ve yalnızca tetikleyicidir; içerik API'den okunur; poller her zaman açıktır; yalnızca poller (webhook'suz) modu da desteklenir. | D-011'in uygulanışı — [ARCHITECTURE.md](ARCHITECTURE.md) §1 ilke 7, §3, §12. | kabul (2026-09-27) |
| D-027 | 2026-09-27 | (ÖK-6) Kritik kuralların tek kaynağı `business_rule` tablosudur; `kb_release` artan tamsayıdır; rollback kuralları değiştirmez. | [ARCHITECTURE.md](ARCHITECTURE.md) §9.2. | kabul (2026-09-27) |
| D-028 | 2026-09-27 | (ÖK-7) KB'nin doğruluk kaynağı DB'dir; `knowledge/` yalnızca PII içermeyen, salt okunur dökümleri tutar. | D-008 ile uyum — [ARCHITECTURE.md](ARCHITECTURE.md) §9.4; [../knowledge/README.md](../knowledge/README.md). | kabul (2026-09-27) |
| D-029 | 2026-09-27 | (ÖK-8) Pilot modlarında `chatRead` çağrılmaz. | D-012'deki yan etki kaygısı — [ARCHITECTURE.md](ARCHITECTURE.md) §4.1. | kabul (2026-09-27) |
| D-030 | 2026-09-27 | (ÖK-9) Yönetim ekranı ayrı porttadır, yalnızca 127.0.0.1/LAN'a bağlanır; uzaktan erişim VPN/SSH tüneliyle. | [ARCHITECTURE.md](ARCHITECTURE.md) §11, §12. | kabul (2026-09-27) |
| D-031 | 2026-09-27 | (ÖK-10) Ham depoda sohbet başına şifreleme ve kripto-silme. | [ARCHITECTURE.md](ARCHITECTURE.md) §6.12, §6.14. | kabul (2026-09-27) |
| D-032 | 2026-09-27 | (ÖK-11) Görsel gönderimi, metin outbox'ı gerçek sistemde doğrulandıktan sonra açılır (`images_enabled=false` ile başlanır). | [ARCHITECTURE.md](ARCHITECTURE.md) §6.5, §8. | kabul (2026-09-27) |
| D-033 | 2026-09-27 | (ÖK-12) Sanal set semantiği (setin kendi stoğu yok; kullanılabilirlik bileşenlerden hesaplanır); B-002 cevabına kadar geçerli. | [ARCHITECTURE.md](ARCHITECTURE.md) §6.7; set sorusu B-002'de. | kabul (2026-09-27) |
| D-034 | 2026-09-27 | (Y9) Canlı mesajların ham kopyası tutulmaz (yalnızca maskeli kopya); ham depo yalnızca içe aktarılan geçmiş içindir; 7/24 servis ana anahtar olmadan çalışır. | Y9 — [ARCHITECTURE.md](ARCHITECTURE.md) §5 (`message`), §6.12. | kabul (2026-09-27) |
| D-035 | 2026-09-27 | Çekirdek teknoloji yığını: Python 3.11, uv, FastAPI, PostgreSQL 16, SQLAlchemy/Alembic, psycopg 3, pytest, ruff, mypy. Barındırma, LLM sağlayıcısı, inventory adaptörü, Notifier ve yedek hedefi D-010 kapsamında açık kalır (B-002, B-004, B-006). | [ARCHITECTURE.md](ARCHITECTURE.md) §13; T-014 iskeleti (`11694f5`). | kabul (2026-09-27) |

## Uygulama kararları (T-014 soruları üzerine, 2026-09-27)

| ID | Tarih | Karar | Gerekçe | Durum |
|---|---|---|---|---|
| D-036 | 2026-09-27 | HTTP istemcisi `httpx` kalır; `httpx2`'ye geçilmez. | T-014 sorusu üzerine Main Agent kararı. Bağlam: Starlette TestClient `httpx2`'yi öneren bir uyarı veriyor, `httpx` çalışıyor ([../pyproject.toml](../pyproject.toml) `filterwarnings`). | kabul (2026-09-27) |
| D-037 | 2026-09-27 | PII maskeleyici tüm URL'leri maskeler; izin listesi (allowlist) çıktı filtresinin işidir. | T-014 sorusu üzerine Main Agent kararı — [ARCHITECTURE.md](ARCHITECTURE.md) §7.2, §7.4. | kabul (2026-09-27) |
| D-038 | 2026-09-27 | VIN, LLM girdisinde maskelenir (`[VIN_1]`); kod tarafındaki uyumluluk değerlendirmesi maskeleyicinin bellek içi eşlemesini kullanır. | T-014 sorusu üzerine Main Agent kararı — [ARCHITECTURE.md](ARCHITECTURE.md) §7.4. | kabul (2026-09-27) |

## Verilen canlı yetkiler

Sahibin verdiği canlı gönderim / dış sisteme yazma yetkileri burada kayıtlıdır (D-006). Her kayıt: tarih, kapsam (hangi işlem, hangi sistem, hangi sınırlar), dayanak (sahibin onayı), gösterilen test kanıtı.

| Tarih | Kapsam | Dayanak | Test kanıtı |
|---|---|---|---|
| — | Henüz verilmiş canlı yetki yok. | — | — |
