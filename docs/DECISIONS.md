# DECISIONS — Kararlar ve kısa gerekçeleri

Kararların **tek kaynağı** bu dosyadır. Durum değerleri: `geçerli` · `kabul (YYYY-MM-DD)` (Main Agent'ın kabul ettiği mimari ve uygulama kararları; geçerli sayılır) · `değiştirildi (→ D-xxx)` · `iptal`. Güven etiketleri: [INTEGRATIONS.md](INTEGRATIONS.md) başındaki tablo.

Sıradaki karar kimliği: **D-047**.

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

Main Agent 2026-09-27'de mimariyi rev.2 olarak kabul etti. D-015–D-021, [ARCHITECTURE.md](ARCHITECTURE.md) §16'daki Main Agent kararları MA-1…MA-7'dir; D-022–D-033, aynı bölümdeki öneriler ÖK-1…ÖK-12'dir (sırasıyla). Rev.1'in "belirsiz gönderimde en fazla bir otomatik yeniden gönderim" önerisi MA-1 ile değiştirildiği için ayrıca kaydedilmedi. Gerekçe sütunundaki § numaraları **ARCHITECTURE rev.2**'ye göredir; rev.2 sahip onayıyla commit edildi (`1f7c2dc`, T-036; [../BLOCKERS.md](../BLOCKERS.md) B-013 çözüldü).

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

## İşletme ve kapsam kararları (2026-09-27)

| ID | Tarih | Karar | Gerekçe | Durum |
|---|---|---|---|---|
| D-039 | 2026-09-27 | **Ödeme yöntemleri:** hepsi kabul edilir — nakit (нал), QR kodla ödeme (СБП/QR), karta havale ve şirketler için banka havalesi (безнал; tutara +%10). **+%10 yalnızca şirketlere (B2B banka havalesi) uygulanır;** tüketiciden kart/QR/СБП için ek ücret alınması yasaktır (ЗоЗПП md. 16.1 p.4, Rospotrebnadzor — T-037, ikincil kaynak). Sahip bunu teyit etti; muhasebeci henüz teyit etmedi. Ödeme yöntemleri müşteriye açık bilgi olduğundan public depoya yazılabilir ([../AGENTS.md](../AGENTS.md) §5 yasağına bu bilgi için istisna). İndirim sınırları, maliyetler ve tedarikçi bilgileri [../BLOCKERS.md](../BLOCKERS.md) B-008 açıkken git dışında kalır. Ödeme **ayrıntıları** yalnızca Avito'nun izin verdiği kanallardan paylaşılır (D-040). **Takip:** output filter'ın nakit için verdiği `PAYMENT_TERMS_UNCONFIRMED` reddi ([../app/safety/filter.py](../app/safety/filter.py)) T-041 ile değiştirildi (`6d013f8`): ödeme ifadesi yalnızca sahibin onayladığı `rule_payment` span'ında serbest, kodun yeni adı `PAYMENT_TERMS_OUTSIDE_RULE` (D-043 → D-l, D-044). | Sahip cevabı ve teyidi (B-005, 2026-09-27); depoya yazma: Main Agent kararı; +%10 sınırı: T-037. | geçerli |
| D-040 | 2026-09-27 | **Avito moderasyonu atlatılmaz.** Sistem, Avito'nun denetimlerini aşacak biçimde tasarlanmaz: ödeme veya iletişim bilgileri metin denetiminden kaçmak için görsel olarak gönderilmez; Avito sohbetlerinde müşteri platform dışına yönlendirilmez. Ödeme bilgileri yalnızca Avito'nun izin verdiği kanallardan paylaşılır. Meşru alternatifler T-037'de araştırılır: Avito'nun doğrulanmış işletme profili istisnası, Avito'nun izin verdiği yerde web sitesi bağlantısı, Avito'nun kendi ödeme/teslimat hizmeti, aramayla web sitesine veya diğer kanallara gelen müşterilere doğrudan hizmet. | Sahibin kuralı: "Platformun erişim sınırlarını, hız sınırlarını ve güvenlik kontrollerini aşmaya çalışma" ([OWNER_REQUEST_2026-09-27.md](OWNER_REQUEST_2026-09-27.md) §3); Товары sohbetlerinde iletişim bilgisi yasağı ([NOTES.md](NOTES.md), [INTEGRATIONS.md](INTEGRATIONS.md) — ikincil kaynak); hesap engeli riski. Main Agent kararı, sahibe bildirildi. | geçerli |
| D-041 | 2026-09-27 | Web sitesi **ayrı bir projedir**; başlangıç dosyalarını T-038 hazırlar. Sahip iki projeyi birleştirene kadar bu projenin kapsamı dışındadır. | Main Agent kararı. | geçerli |
| D-042 | 2026-09-27 | **Messenger API tarifesi için sahibe üç seçenek sunulur:** (1) tam API otomasyonu için «Максимальный» tarifeye geçmek; (2) Messenger API kullanmayan "elle aktarma" pilotu: sahip müşteri mesajını yönetim ekranına kopyalar, asistan taslak cevap üretir, sahip cevabı Avito'ya yapıştırır — `draft_only` moduyla uyumlu; (3) tarayıcı otomasyonu üretim seçeneği **değildir** (D-011). Mevcut tarifenin gerçekte neye izin verdiğini T-039'un salt okunur erişim kontrolü gösterecek. | Sahip cevabı (2026-09-27): Pro profili, Базовый tarife (engel: [../BLOCKERS.md](../BLOCKERS.md) B-007); spec kopyasına göre (canlı doğrulanmadı) Товары için Messenger API «Максимальный» gerektirir ([INTEGRATIONS.md](INTEGRATIONS.md) §3.2). Main Agent kararı. | geçerli |
| D-045 | 2026-09-27 | **Pilot barındırma = sahibin Windows bilgisayarı.** Servisler oturum açmadan başlayan Windows servisleri olarak çalışır; uyku kapatılır; webhook'suz, yalnızca poller modu (D-026) — açık port ve tünel yok; yönetim ekranı yalnızca localhost'a bağlanır; yedekler makine dışında tutulur. 152-FZ yerelleştirme sorusu teyit edilene kadar beklemede: veri sahibin bilgisayarında kalır, LLM sağlayıcısı sonra seçilir ([../BLOCKERS.md](../BLOCKERS.md) B-006, B-010). Gerekirse sonra sunucuya taşınır. | Sahip cevabı (2026-09-27): sistem önce kendi bilgisayarına kurulsun, gerekirse sonra sunucuya geçilsin ([../BLOCKERS.md](../BLOCKERS.md) B-004). [ARCHITECTURE.md](ARCHITECTURE.md) §12: "PC, yalnızca poller" seçeneği ve Windows'ta oturum açmadan başlayan servis gereği; belge Windows yerine Linux VPS'i önermişti, pilot için sahip tercihi seçildi. Main Agent kararı. | geçerli |
| D-046 | 2026-09-27 | **Envanter kaynağı = sahibin Obsidian Vault'u (salt okunur).** Vault sahibin doğruluk kaynağı olarak kalır (D-008). Veritabanımız Vault'un `fetched_at` zaman damgalı, salt okunur senkron kopyasını tutar. Vault'a geri yazma (ör. rezervasyon) yalnızca sahibin ayrı onayıyla yapılır; Vault izinsiz değiştirilmez ([../AGENTS.md](../AGENTS.md) §6). Sıra: T-043 (salt okunur, anonimleştirilmiş Vault taraması) → salt okunur Vault envanter adaptörünün tasarımı. | Sahip cevabı (2026-09-27): stok, fiyat ve fotoğrafların hepsi Vault'ta, ayrı depo yazılımı yok ([../BLOCKERS.md](../BLOCKERS.md) B-002). Main Agent kararı. | geçerli |

## Output filter kararları (T-034, T-041)

Kodda (`app/safety/`) kararlar T-034 brief'indeki harf kimlikleriyle anılır ("D-a" … "D-l"); karşılıkları D-043'tedir. Brief: [../tasks/T-034/brief.md](../tasks/T-034/brief.md). Testler yalnızca sentetik veriyle ([TEST_REPORT.md](TEST_REPORT.md)).

### D-043 — T-034 filtre kararları (D-a…D-l)

- **Tarih:** 2026-09-27 · **Kaynak:** T-034 brief'i (T-032 bulgularının düzeltmesi), Main Agent kararları · **Durum:** kabul (2026-09-27); D-l değiştirildi (aşağıda).

| Alt kimlik | Karar (tek satır özet) | Durum |
|---|---|---|
| D-a | Maskeleyici ve filtre ortak normalleştirme katmanını (`app/safety/normalize.py`) kullanır; gizleme girişimi `OBFUSCATION`, geçersiz karakter `INVALID_TEXT` ile reddedilir. | kabul |
| D-b | Filtre kalıpları genişletildi (T-032'nin yeniden üretimleri regresyon testi). | kabul |
| D-c | Olumlu uyumluluk iddiası ("подойдёт") doğrulama olmadan reddedilir (`UNVERIFIED_FITMENT`); soru/çekince (hedge) cümlesi istisnadır. | kabul; çekince istisnası D-044 ile daraltıldı |
| D-d | URL host'u katı biçimde ayrıştırılır; izin listesindeki URL de temiz olmalıdır. | kabul |
| D-e | Liste beklenen yerde tek `str` argümanı `TypeError` verir. | kabul |
| D-f | Şablon muafiyeti yalnızca kodun verdiği span'lara (başlangıç, bitiş) göredir; şablon metnini tekrar eden metin muaf olmaz. | kabul; D-044'te tipli span'lara genişletildi |
| D-g | Filtre fail-closed çalışır; sahip düzeltmesinde bulgulu parça `overridable` işaretlenir, gönderim denetimli sahip onayı ister. | kabul |
| D-h | Maskeleyicide handle ve telefon tespiti düzeltmeleri. | kabul |
| D-i | `extract_part_number_candidates` maskelenmemiş müşteri metninde, maskelemeden önce çalışır; maskeleyicinin telefon sandığı parça numaraları katalog eşleştirmesine yine ulaşır. | kabul |
| D-j | `allowed_literals` sözleşmesi: yalnızca olgu kağıdı ve ürün kayıtlarından gelir, müşteri metninden türetilmez; yazım varyantları `literal_variants` ile eklenir. | kabul |
| D-k | Muhafazakâr parça uzunluğu: ≤1000 UTF-16 birimi **ve** ≤1000 UTF-8 bayt (`measure_part`; Avito'nun sayım birimi doğrulanmadı). | kabul |
| D-l | Nakit ödeme ifadesi işletme kuralları belli olana kadar reddedilir (`PAYMENT_TERMS_UNCONFIRMED`). | değiştirildi (→ D-039, D-044): ödeme ifadesi yalnızca sahibin onayladığı `rule_payment` span'ında serbest |

### D-044 — T-041 filtre kararları (T-032b doğrulamasından)

- **Tarih:** 2026-09-27 · **Kaynak:** T-032b doğrulaması (düzeltmelerle kabul), Main Agent kararları · **Durum:** geçerli — T-041 ile uygulandı (`6d013f8`); bağımsız doğrulaması T-045 ([../TASKS.md](../TASKS.md)).

- **Tipli span'lar:** `rule_payment`, `rule_generic`, `offer`, `confirmation`, `bot_disclosure`, `wait_message`; her türün kendi kod başına muafiyetleri vardır.
- `PAYMENT_CARD` ve `CONTACT_PHONE` sert engeldir; sahip düzeltmesinde de geçersiz kılınamaz.
- Çekince (hedge) istisnası yalnızca soru biçimlerine ve gelecek zamanlı doğrulama fiillerine daraltıldı.
- Unicode izin listesi (whitelist) politikası.
- Bölünmüş kelimeler için sıkıştırılmış görünümde (compact view) eşleştirme.
- `mask()` girdi sınırı 50 bin karakter; aşan girdi sahibe gider.
- Küçük sayı kelimeleri pilot boyunca reddedilmeye devam eder; etkisi ölçülecek.
- Sahibin ödeme kuralı metni "по QR-коду (СБП)" der, "по номеру телефона" demez (D-039).
- `PAYMENT_TERMS_UNCONFIRMED` kodunun yeni adı `PAYMENT_TERMS_OUTSIDE_RULE`.

## Verilen canlı yetkiler

Sahibin verdiği canlı gönderim / dış sisteme yazma yetkileri burada kayıtlıdır (D-006). Her kayıt: tarih, kapsam (hangi işlem, hangi sistem, hangi sınırlar), dayanak (sahibin onayı), gösterilen test kanıtı.

| Tarih | Kapsam | Dayanak | Test kanıtı |
|---|---|---|---|
| — | Henüz verilmiş canlı yetki yok. | — | — |
