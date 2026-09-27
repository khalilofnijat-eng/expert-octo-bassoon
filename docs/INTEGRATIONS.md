# INTEGRATIONS — Bağlantılar ve yetenekler

Engeller: [../BLOCKERS.md](../BLOCKERS.md). Görevler: [../TASKS.md](../TASKS.md). Kararlar: [DECISIONS.md](DECISIONS.md).

**Güven etiketleri** (bu dosyada ve diğer kayıtlarda aynı anlamda kullanılır):

| Etiket | Anlamı |
|---|---|
| Doğrulanmış | Komut çıktısı veya test kaydı var (kanıtı bu dosyada, §2 ya da ilgili satırda). |
| resmî spec'in topluluk kopyası — resmî kaynakla karşılaştırılmadı, canlı doğrulanmadı | Avito'nun resmî OpenAPI spec'inin GitHub'daki topluluk kopyalarından alındı (§6). Resmî portal bu ortamdan açılamadığı için karşılaştırılmadı (B-009); canlı çağrı yapılmadı. |
| ikincil kaynak | Üçüncü taraf blog, entegratör veya forum; çoğu yalnızca arama özetiyle görüldü. |
| doğrulanamadı | Hiçbir kaynakta bulunamadı ya da kaynaklar çelişiyor. |

Kaynak: T-001 ve T-002 teslim metinleri (Main Agent kabul etti). Metinlerin kendisi repoda yok ([../TASKS.md](../TASKS.md) → B-012 listesi); kabul edilen bulguların kalıcı özeti bu dosyadadır (§2–§6).

## 1. Genel tablo

| Entegrasyon | Amaç | Yöntem | Durum | Yetenekler | Kanıt | Engel |
|---|---|---|---|---|---|---|
| Avito resmî API (Messenger + Items) | Yeni mesaj alma, yetkili gönderim, geçmiş okuma, ilan bilgisi | Resmî REST API, OAuth2 `client_credentials`; webhook + periyodik uzlaştırma (D-011); kendi ince istemcimiz (D-013) | seçildi, bağlı değil | §3 — **hiçbiri canlı doğrulanmadı** | §3–§6 (T-002) | B-007, B-009, B-011 |
| Avito web arayüzü / Chrome | Yalnızca API'nin ulaşamadığı eski geçmiş için, tek seferlik (D-011) | Sahibin bilgisayarındaki oturum — BİLİNMİYOR | erişim yok | — | §2.4 (tarayıcı kontrol aracı yok); riskler §5 | B-001 |
| Depo / muhasebe sistemi | Ürün, stok, fiyat, rezervasyon, sipariş | BİLİNMİYOR | bilinmiyor | — | — | B-002 |
| Ürün fotoğrafları | Gerçek stok kaydına bağlı fotoğraflar | BİLİNMİYOR | bilinmiyor | — | — | B-002 |
| Obsidian Vault | Proje belgelerinin son yerleşimi | BİLİNMİYOR | bilinmiyor | — | — | B-003 |
| GitHub | Kod ve geliştirme sürümleme | Git, HTTPS remote (§2.3) | çalışıyor; depo **public**; varsayılan ve tek dal `claude/youthful-goldberg-l427nm` (D-014) | Doğrulanmış: okuma ve push | T-011 (2026-09-27): GitHub API `search_repositories` → `default_branch: "claude/youthful-goldberg-l427nm"`, `visibility: "public"`, `private: false`; `list_branches` → yalnızca bu dal (sha `9b4bdc1`). T-013 (2026-09-27): `git status` → yerel dal `origin` ile eşit (HEAD `667d96d`). İlk push öncesi gözlem: §2.3. | B-008 |
| Bulut geliştirme ortamı | Kod geliştirme, birim testleri | Geçici bulut konteyner | çalışıyor; **avito.ru engelli** (403) | Doğrulanmış (§2): §2.1'deki araçlar kurulu ve sürümleri okunuyor; PyPI'dan paket indirme çalışıyor; PyPI, npm, GitHub ve Anthropic API'ye HTTPS bağlantısı kuruluyor. Doğrulanmış olumsuz: www/api/developers.avito.ru'ya erişim yok; sahibin tarayıcısını kontrol eden araç yok. Doğrulanmadı: headless Chromium'un başlatılması (yalnızca kurulum dizini görüldü), 7/24 çalışma. | §2 (T-001 komutları ve çıktıları) | B-009 |
| AI hizmeti | Cevap taslağı üretimi | BİLİNMİYOR | seçilmedi | — | — | B-006, B-010 |

## 2. T-001 kanıt özeti (bulut ortamı, 2026-09-27)

T-001 (Keşif agent'ı), yaklaşık 17:52 UTC, yalnızca okuma yapan komutlarla. Bu bir anlık görüntüdür; konteyner geçicidir.

### 2.1 Araç sürümleri

| Araç | Sürüm |
|---|---|
| İşletim sistemi | Ubuntu 24.04.4 LTS, x86_64; 4 CPU, 15 GiB RAM (`uname -a`, `nproc`, `free -h`) |
| python3 / pip | 3.11.15 / 24.0 |
| uv / poetry | 0.8.17 / 2.3.3 |
| node / npm | v22.22.2 / 10.9.7 |
| docker | 29.3.1 |
| psql / redis-cli | 16.13 / 7.0.15 |
| git | 2.43.0 |
| sqlite3 CLI | **yok** |
| Playwright / Chromium | `/opt/pw-browsers` altında `chromium-1194` ve `chromium_headless_shell-1194`; `playwright` CLI mevcut. İzole profil, sahibin oturumuyla ilgisi yok. |

Paket indirme testi: `pip download --no-deps -d <scratchpad> requests` → başarılı (`requests-2.34.2`); depoya veya sisteme kurulum yapılmadı.

### 2.2 Ağ testleri

Komut (her URL için bir GET): `curl -sS -o /dev/null -w "HTTP_STATUS:%{http_code}" <URL>`

| URL | Sonuç | Yorum |
|---|---|---|
| https://www.avito.ru | `curl: (56) CONNECT tunnel failed, response 403` | erişilemiyor |
| https://api.avito.ru | aynı (403) | erişilemiyor |
| https://developers.avito.ru | aynı (403) | erişilemiyor |
| https://pypi.org/simple/ | HTTP 200 | erişilebilir |
| https://registry.npmjs.org | HTTP 200 | erişilebilir |
| https://api.anthropic.com | HTTP 404 | bağlantı kuruldu (kök yol için beklenen) |
| https://github.com | HTTP 400 | bağlantı kuruldu (kök yol için beklenen) |

Proxy durumu: `curl -sS "$HTTPS_PROXY/__agentproxy/status"` → proxy etkin; son reddedilen bağlantılar arasında avito.ru alt alanları (developers, www, support, api) ve web.archive.org, "gateway answered 403 to CONNECT (policy denial or upstream failure)" ile. Politika reddi tekrar denenmedi, TLS doğrulaması kapatılmadı. T-002 de aynı engeli gördü (curl ve WebFetch ile avito.ru okunamadı). Sonuç: bu ortamdan avito.ru'ya HTTPS erişimi yok (B-009).

### 2.3 Depo gözlemi (ilk push'tan önce)

- `git remote -v` → `origin https://github.com/khalilofnijat-eng/expert-octo-bassoon` (HTTPS, SSH değil).
- O an yerel depoda commit yoktu (`git status` → "No commits yet").
- GitHub API `search_repositories` (`repo:khalilofnijat-eng/expert-octo-bassoon`) → `private: false`, `visibility: "public"`, `default_branch: "main"`, `size: 0`; `list_branches` → `[]`.
- Güncel gözlem (ilk push'tan sonra): §1 → GitHub satırı.

### 2.4 Tarayıcı ve masaüstü kontrol araçları

`ToolSearch` sorguları: "chrome browser extension control" ve "computer use remote devices desktop control". Sonuçta `mcp__claude-in-chrome__*`, `mcp__Claude_Browser__*`, `mcp__remote-devices__*` veya computer-use aracı **yok**. Bu ortam sahibin Chrome'una ve masaüstüne ulaşamıyor (B-001); tek tarayıcı, §2.1'deki izole headless Chromium.

### 2.5 Kimlik bilgisi değişkenleri (yalnızca adlar)

Komut: `env | cut -d= -f1 | grep -Ei 'AVITO|ANTHROPIC|OPENAI|API_KEY|CLIENT_ID|CLIENT_SECRET'` → yalnızca `ANTHROPIC_BASE_URL` (değeri okunmadı). Avito kimlik bilgisi değişkeni yok (B-011).

## 3. Avito resmî API — uç noktalar (T-002)

Bu bölümün tamamı, aksi yazılmadıkça: **resmî spec'in topluluk kopyası — resmî kaynakla karşılaştırılmadı, canlı doğrulanmadı.**

Base URL `https://api.avito.ru`. `{user_id}` sayısal hesap kimliğidir ve `GET /core/v1/accounts/self` ile alınır. Kimlik doğrulama: `Authorization: Bearer <token>`.

### 3.1 Uç nokta tablosu

| Yöntem | Yol | Ana parametreler | Koşullar ve sınırlar |
|---|---|---|---|
| POST | `/token` | `grant_type=client_credentials`, `client_id`, `client_secret` | Satıcının kendi hesabı. Belgelenen ömür 24 saat; bir örnekte `expires_in: 3600` → yanıttaki `expires_in` esas alınır. Refresh token yok; süre dolunca yeniden alınır. (`authorization_code` akışı da var; bizim senaryoda gerekmez.) |
| GET | `/core/v1/accounts/self` | — | `user_id` kaynağı. 401, 403 ("Неверный Token/Oauth Scope"), 500, 503 belgelenmiş. |
| GET | `/messenger/v2/accounts/{user_id}/chats` | `item_ids`, `unread_only`, `chat_types` (u2i/u2u/a2u; varsayılan u2i), `limit`, `offset` | `limit` açıklamada "<100", varsayılanı 100 (çelişki) → ≤ 99, tercihen 50. `offset` üst sınırı ve sıralama belgelenmemiş. Okuma yan etkisi belgelenmemiş (doğrulanamadı). |
| GET | `/messenger/v2/accounts/{user_id}/chats/{chat_id}` | — | İlan bağlamı `context.value`: id, title, price_string, url, status_id, 140x105 ana görsel, görsel sayısı; kullanıcılar; son mesaj. Kullanıcı ID'leri hash'lenmiş olabilir → kalıcı anahtar `chat_id`. |
| GET | `/messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/` | `limit` (<100), `offset` | **Sohbeti okundu yapmaz.** Alanlar: id, author_id, created, direction, type, content, is_read, read, quote. Tipler: text, image, link, item, location, call, deleted, voice, system. Geçmiş derinliği belgelenmemiş (§4). |
| POST | `/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages` | Gövde `{"type":"text","message":{"text":"…"}}` | Yalnızca metin; **en fazla 1000 karakter**. Spec şemasındaki `required: ["url"]` hatalı; şemaya körü körüne güvenilmez. |
| POST | `/messenger/v1/accounts/{user_id}/uploadImages` | multipart alanı `uploadfile[]` | JPEG/HEIC/GIF/BMP/PNG; en fazla 24 MB ve 75 MP; istek başına 1 görsel. |
| POST | `/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/image` | Gövde `{"image_id":"…"}` | Önce `uploadImages`. Görsel ve metin ayrı mesajlardır. |
| POST | `/messenger/v1/accounts/{user_id}/chats/{chat_id}/messages/{message_id}` | — | Mesaj silme: **gönderimden en geç 1 saat içinde**; mesaj geçmişte `deleted` tipiyle kalır. |
| POST | `/messenger/v1/accounts/{user_id}/chats/{chat_id}/read` | — (scope `messenger:read`) | `chatRead`: sohbeti okundu yapar. Karşı tarafa görünür etkisi belgelenmemiş (doğrulanamadı). |
| POST | `/messenger/v3/webhook` | Gövde `{"url":"…"}` | Kayıtlı URL 2 saniye içinde 200 OK dönmeli. Ayrıntı §3.3. |
| POST | `/messenger/v1/subscriptions` | — | Webhook aboneliklerini listeler: `subscriptions[{url, version}]`. |
| POST | `/messenger/v1/webhook/unsubscribe` | Gövde `{"url":"…"}` | Abonelikten çıkma. |
| POST | `/messenger/v2/accounts/{user_id}/blacklist` | `users[{user_id, context{item_id, reason_id 1–4}}]` | Kara liste. |
| GET | `/messenger/v1/accounts/{user_id}/getVoiceFiles` | `voice_ids` | Yalnızca okuma; opus/.mp4; bağlantı 1 saat geçerli. Sesli mesaj gönderme belgelenmemiş. |
| GET | `/core/v1/items` | `per_page` (<100), `page`, `status`, `updatedAtFrom`, `category` | Kendi ilanları: id, title, price, status, url, category, address. **Dakikada 25 istek**; 429 ile `X-RateLimit-Limit`, `X-RateLimit-Remaining`. Çalışanların ilanları dönmez. |
| GET | `/core/v1/accounts/{user_id}/items/{item_id}/` | — | Kısmi: status, url, start/finish_time, `autoload_item_id`, vas. Başlık, fiyat ve fotoğraf dönmez. **Dakikada 500 istek.** |
| GET | `/autoload/v2/items/avito_ids`, `/autoload/v2/items/ad_ids` | — | Autoload feed ID'leri ↔ Avito ID'leri; yalnızca Autoload kullananlar için. Autoload v2/v3 rapor uçları 08.03.2027'de 410 Gone dönecek; v4 kullanılmalı. |

Sayım: Messenger 13 uç, Items/Autoload 3 uç (D-013).

### 3.2 Genel koşullar

- **Erişim şartı (B-007):** Spec'teki metin: "В Товарах и Работе Messenger API доступен только на уровне подписки «Максимальный». В Услугах — «Расширенный» и «Максимальный»." Yedek parçanın "Товары" kapsamında olduğu: ikincil kaynak, doğrulanamadı. Şartın 6 Kasım 2025'ten beri uygulandığı ve fiyatın ~4 000 ₽/ay'dan başladığı: ikincil kaynak.
- **Hesap hiyerarşisi:** Messenger API yalnızca şirketin ana hesabıyla tam çalışır; çalışan anahtarıyla sohbet listesi eksik gelir, okuma ve gönderme hata verir.
- **Amaç:** Messenger API, "CRM ile iki yönlü entegrasyon" için sunuluyor. Birçok üçüncü taraf entegratör ve AI-bot hizmeti aynı API'yi kullanıyor (ikincil kaynak).
- **Hız sınırı:** Messenger uçları için belgelenmemiş (spec'in diğer bölümlerinde dakikada 5–1000 arası). Items sınırları §3.1'de.
- **Hata gövdesi:** uca göre değişiyor: `{code,message}`, `{error:{code,message}}` veya `{errors:[…]}`.
- **Sistem mesajları:** `type=system`, `content.flow_id`; örn. `flower_161071` = satıcının ayarladığı otomatik yanıtlar.
- **Dosya/video gönderme:** belgelenmemiş. Gelen file/video/appCall mesajlarının içeriği boş döner.

### 3.3 Webhook

- Payload (v3): `{id, version, timestamp, payload: {type: "message", value: {id, chat_id, user_id, author_id, created, type, chat_type, content, item_id (yalnız u2i), read, published_at}}}`. `user_id` her zaman webhook'un kayıtlı olduğu hesaptır.
- Kendi gönderdiğimiz mesajın webhook'la gelip gelmediği belgelenmemiş.
- Tekrar deneme (retry), sıralama ve teslim garantisi belgelenmemiş (doğrulanamadı) → periyodik uzlaştırma yoklaması gerekir (D-011).
- HTTPS zorunluluğu açıkça yazmıyor, ama tüm örnekler https (doğrulanamadı).
- İmza: topluluk `x-avito-messenger-signature` başlığının (64 hex) geldiğini ve algoritmanın yayımlanmadığını bildiriyor (ikincil kaynak).

## 4. Avito — belirsiz ya da doğrulanamayan konular

- Geçmişin ne kadar geriye okunabildiği: belgelenmemiş (doğrulanamadı) → T-010 ölçecek (D-012).
- Messenger uçlarının hız sınırı: belgelenmemiş.
- Webhook imza algoritması, retry ve teslim garantisi: §3.3.
- İlanın tam fotoğraf seti, açıklaması, parça numarası: bunları döndüren uç bulunamadı (doğrulanamadı). Sohbet bağlamında yalnızca 140x105 ana görsel var.
- `chatRead`'in alıcı tarafta "okundu" gösterip göstermediği: doğrulanamadı.
- Messenger dışındaki uçların da ücretli olup olmadığı: doğrulanamadı.
- API kullanım şartları (https://www.avito.ru/legal/pro_tools/public-api): bu ortamdan okunamadı (B-009); canlıya geçmeden okunmalı.

## 5. Avito web arayüzü (tarayıcı otomasyonu) — riskler

T-002 değerlendirmesi. D-011'de tarayıcı otomasyonunun birincil kanal olmamasının gerekçesidir.

1. Kullanım şartlarına aykırılık ve hesabın engellenmesi: Avito şartlarının bot veya script ile izinsiz veri toplamayı yasakladığı ve botların hızla engellendiği bildiriliyor (ikincil kaynak; madde metni doğrulanamadı).
2. Anti-bot önlemleri ve CAPTCHA.
3. Arayüz değiştiğinde otomasyonun kırılması.
4. Sahibin oturum çerezlerinin otomasyona açılması.
5. Arayüzde sohbet açmanın sohbeti okundu yapabilmesi (doğrulanamadı).

## 6. Kaynaklar ve topluluk kütüphaneleri (T-002, erişim 2026-09-27)

Spec'in topluluk kopyaları (Messenger bölümü dört kopyada tutarlı):
- [MissiaL/avito-api](https://github.com/MissiaL/avito-api), commit 8e9bafc9 (2026-07-16): `references/avito-api-openapi.json`, `sections/*.md`. README'ye göre portalın `GET /web/1/openapi/list` ve `/web/1/openapi/info/<slug>` uçlarından toplanmış.
- kozandlov/avito-python-sdk: `specs/raw/messenger.json`, `specs/patched/messenger.json`.
- elchin92/avito-mcp: `swaggers/messenger.json` (kozandlov kopyasıyla bayt olarak aynı).
- kmlebedev/avito-gen-api: `swagger/messenger.json` — eski sürüm; abonelik cümlesi yok.

Topluluk kütüphaneleri (resmî değil):
- kozandlov/avito-python-sdk: PyPI paketi `avito-python-sdk`, import adı `pyavitoapi`, async; lisansı **AGPL-3.0** (kapalı kaynak üründe risk).
- MissiaL/avito-api, elchin92/avito-mcp, kmlebedev/avito-gen-api: spec ve yardımcı araç kopyaları.
- Sonuç (D-013): SDK'ya bağlanmak yerine §3.1'deki uçlar için kendi ince istemcimiz yazılır.

Resmî adresler (bu ortamdan erişilemedi — B-009): https://developers.avito.ru/api-catalog, https://developers.avito.ru/api-catalog/messenger/documentation, https://developers.avito.ru/applications, https://www.avito.ru/legal/pro_tools/public-api.
