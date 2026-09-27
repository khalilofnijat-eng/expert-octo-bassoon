# T-010 — Salt okunur Avito geçmiş derinlik ölçüm betiği

- **Aşama:** 3 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** atanmadı (betiği yazan uygulama agent'ı; çalıştıran **sahip**)
- **Tarih:** 2026-09-27 (kapsam: T-016)

## Amaç

Tam geçmiş aktarımından (T-006, T-020) önce, Avito Messenger API'sinin gerçek davranışını **hiçbir yan etki yaratmadan** ölçmek (D-012). Betik yalnızca okur, sahibin makinesinde sahibin kendi kimlik bilgileriyle çalışır ve yalnızca toplu sayılar, tarihler ve biçimler raporlar. Sonuçlar [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §10.1'deki doğrulanmamış varsayımları (M1–M9) kesinleştirir.

## Kapsam

- **Dahil:** GET-only ölçüm betiği; M1–M9 ölçümleri ve okundu yan etkisinin canlı doğrulaması (aşağıdaki tablo); izin listesiyle sınırlanmış istemci; toplu çıktı raporu; mock üzerinde testler.
- **Hariç:** Mesaj içeriğinin veya ham yanıtların saklanması; tam aktarım (T-020); gönderim gerektiren ölçümler (M4'ün tamamı pilotun ilk `approve_to_send` gönderimlerinde yapılır — ARCHITECTURE §10.1); tarayıcı kullanımı; bu bulut ortamından Avito çağrısı (B-009).

## Bağımlılıklar

- **Görevler:** T-016 (bu kapsam), T-017 (Avito gateway okuma istemcisi + spec tabanlı mock; betik bu istemciyi kullanır).
- **Engeller:** B-007 (Messenger API erişimi / abonelik, ana hesap anahtarı), B-009 (bu ortamdan avito.ru'ya erişim yok → betik sahibin makinesinde çalışır), B-011 (kimlik bilgileri sahibin makinesinde ortam değişkeni olarak). İlgili: B-014 (çalışan hesapları — M6 yorumunu etkiler).
- Uç noktalar ve güven etiketleri: [docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md) §3.1 (hiçbiri canlı doğrulanmadı).

## İzinli ve yasak çağrılar

İstemci bir **izin listesiyle** çalışır; listede olmayan her (yöntem, yol) çağrısı ağ isteği yapılmadan hata verir.

| İzinli | Amaç |
|---|---|
| `POST /token` (`client_credentials`) | Kimlik doğrulama. Tek POST istisnasıdır; Avito'da veri değiştirmez. Token yalnızca bellekte tutulur. |
| `GET /core/v1/accounts/self` | `user_id` |
| `GET /messenger/v2/accounts/{user_id}/chats` | Sohbet listesi (M1, M7, M8, okundu kontrolü) |
| `GET /messenger/v2/accounts/{user_id}/chats/{chat_id}` | Sohbet detayı (M9) |
| `GET /messenger/v3/accounts/{user_id}/chats/{chat_id}/messages/` | Mesajlar (M2, M3, M5, M6, M8, M9) |
| `GET /messenger/v1/accounts/{user_id}/getVoiceFiles` ve mesajdaki ek dosya URL'lerine GET | Yalnızca M8 ek dosya ömrü; içerik diske yazılmaz, yalnızca HTTP durumu ve boyut sayılır. |

**Yasak (kod düzeyinde engellenir):** `chatRead` (`…/chats/{chat_id}/read`), mesaj gönderme (metin ve görsel), `uploadImages`, mesaj silme, webhook abone olma/listeleme/abonelikten çıkma (`/messenger/v3/webhook`, `/messenger/v1/subscriptions`, `/messenger/v1/webhook/unsubscribe`), kara liste ve Avito'da bir şey yazan/değiştiren diğer her çağrı ([AGENTS.md](../../AGENTS.md) §6).

## Çalışma kuralları

- **Sayfalama:** `limit` ≤ 99 (varsayılan 50; INTEGRATIONS §3.1). İlk çalıştırma için sohbet ve sayfa sayısı üst sınırı yapılandırılabilir (ör. önce küçük bir örneklem).
- **Hız:** Messenger limitleri belgelenmemiş; muhafazakâr ve ayarlanabilir bir istek hızı kullanılır (ARCHITECTURE §6.10). Paralel istek yoktur.
- **Durma:** 401, 403 veya 429 alınınca betik **hemen durur**, yeniden denemez ve o ana kadarki toplu raporu durma nedeniyle birlikte yazar. 5xx ve zaman aşımında sınırlı sayıda geri çekilmeli yeniden deneme, sonra aynı şekilde durma.
- **Kesilme:** Ctrl+C her an güvenlidir (yan etki yok); o ana kadarki toplu rapor yazılır.
- **Kimlik bilgileri:** `AVITO_CLIENT_ID`, `AVITO_CLIENT_SECRET` yalnızca sahibin makinesindeki ortam değişkenlerinden veya `.env` dosyasından okunur ([BLOCKERS](../../BLOCKERS.md) B-011); sohbete, loglara ve rapora yazılmaz. Anahtar şirketin **ana** hesabından olmalıdır (B-007).
- **Veri:** Ham yanıtlar ve mesaj içeriği yalnızca bellekte işlenir; diske, loglara ve rapora yazılmaz. Rapor depo dışındaki bir yola yazılır.

## Ölçüm kalemleri

Kaynak: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §10.1. Her kalemin raporu yalnızca sayı, tarih ve biçim içerir.

| # | Soru | Yöntem (salt okunur) | Rapor çıktısı |
|---|---|---|---|
| M1 | Sohbet listesi son etkinliğe göre mi sıralı? | Aynı listeyi arka arkaya iki kez al; sıralamayı son mesaj zamanlarıyla karşılaştır. | Sıra ihlali sayısı; iki listeleme arasındaki sıra farkı sayısı; sonuç (sıralı / sırasız / belirsiz). |
| M2 | Mesaj listesinin sıralaması ve `offset` kararlılığı | Örneklem sohbetlerde sayfaları gez, sonra yeniden listele; sayfalar arası tekrar eden ve atlanan kimlikleri say. | Sıralama yönü; tekrar/atlama sayıları; yeniden listelemede yeni kimlik sayısı. |
| M3 | Kendi mesajlarımızın `author_id` değeri = `user_id` mi; `direction` alanının anlamı | Geçmişteki mesajlarda `author_id == user_id` ile `direction` değerlerini çapraz say. | Çapraz tablo (sayılar); sonuç. |
| M4 | Avito gönderilen metni normalize ediyor mu? (kısmi) | Yalnızca geçmişten: kendi mesajlarımızda satır sonu, art arda boşluk, emoji, baş/son boşluk bulunma sıklığı. Tam ölçüm pilotta. | Sayılar; "kısmi, pilotta tamamlanacak" notu. |
| M5 | Автоответы'nin görünümü (`type=system`, `content.flow_id`) | `type=system` mesajları ve `flow_id` alanının varlığını say. | Sayılar; `flow_id` önek biçimi (değerler yazılmaz). |
| M6 | Çalışan hesaplarından gelen mesajların `author_id`'si | Her sohbette yazar kümesini çıkar: `user_id`, karşı taraf ve `system` dışındaki yazarları say. | Böyle yazar içeren sohbet ve mesaj sayısı (B-014 ile birlikte yorumlanır). |
| M7 | Karşı taraf kimliğinin kararlılığı | Karşı taraf kimliklerinin birden fazla sohbette görülüp görülmediğini say. | Farklı kimlik sayısı; birden fazla sohbette görülen kimlik sayısı. |
| M8 | Geçmiş derinliği ve ek dosya URL'lerinin ömrü | En eski ve en yeni mesaj tarihleri; aylık mesaj sayısı; ek dosyaları yaş gruplarına göre sınırlı sayıda GET ile dene. | Tarih aralığı; aylık histogram; yaş grubuna göre ek indirme başarı/hata sayıları. |
| M9 | Sohbet detayındaki karşı taraf kimliği, mesajlardaki `author_id` ile aynı biçimde mi? | Aynı sohbette detaydaki kullanıcı kimlikleri ile müşteri mesajlarının `author_id` değerlerini karşılaştır. | Eşleşen/eşleşmeyen sohbet sayısı; her iki alanın biçimi (uzunluk, karakter sınıfı: sayısal/hex/diğer). |
| Okundu | **Okundu yan etkisi olmadığı canlı doğrulanır** (mesaj okumak sohbeti okundu yapmaz — INTEGRATIONS §3.1, canlı doğrulanmadı) | `unread_only=true` listesinden okunmamış bir sohbet seç; mesajlarını GET ile oku; listeyi ve mesajların `is_read`/`read` alanlarını yeniden oku. Sahip ayrıca kendi Avito arayüzünde sohbetin hâlâ okunmamış göründüğünü kontrol edebilir. | Önce/sonra okunmamış sohbet ve mesaj sayıları; sonuç (değişmedi / değişti). Karşı tarafın gördüğü durum API'den gözlenemez; bu sınır raporda yazılır. |

## Çıktı biçimi

- Tek bir toplu rapor (makine okunur biçim + kısa Türkçe özet): çalışma tarihi (UTC), betik sürümü/commit'i, kullanılan parametreler (limit, hız, üst sınırlar), yapılan istek sayısı (uç nokta başına), durma nedeni (varsa), M1–M9 ve okundu sonuçları.
- **Yalnızca toplu sayılar, tarihler ve biçimler.** Rapor şunları içermez: mesaj metni, ad, telefon, ilan başlığı, sohbet/mesaj/kullanıcı kimliklerinin değerleri, URL'ler, token.
- Sahip raporu Main Agent'a iletir; hangi sonuçların kayda ([docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md) §4, [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §10.1) geçeceğine Main Agent karar verir.

## Dosya sahipliği

- Yazabileceği dosyalar: betik ve testleri (yerleri görev atanırken Main Agent'ça belirlenir; ör. `scripts/` ve `tests/`).
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.

## Beklenen çıktı

- Commit edilmiş betik ve mock üzerinde geçen testler; sahibin çalıştırması için kısa Türkçe talimat ([docs/RUNBOOK.md](../../docs/RUNBOOK.md) girdisi Dokümantasyon agent'ına iletilir).
- Teslim raporu: Main Agent'a **metin olarak** ([rapor şablonu](../_TEMPLATE/report.md)); rapor dosyası beklenmez (B-012).

## Kabul ölçütleri

- [ ] İstemci yalnızca yukarıdaki izin listesindeki çağrıları yapar; `chatRead` ve yasak listedeki her çağrı için ağ isteği yapılmadan reddedildiğini gösteren test var.
- [ ] Mock üzerinde uçtan uca çalıştırma: M1–M9 ve okundu kontrolünün her biri raporda bir sonuç üretir (sentetik olarak işaretli).
- [ ] 401, 403 ve 429 durumlarında betiğin durduğu, yeniden denemediği ve durma nedenini raporladığı testle gösterilir.
- [ ] Sayfalama `limit` ≤ 99 kullanır; istek hızı ve üst sınırlar yapılandırılabilir; paralel istek yok.
- [ ] Rapor ve loglarda mesaj içeriği, kimlik değeri, URL veya token bulunmadığını doğrulayan test var (sentetik PII içeren mock verisiyle).
- [ ] Ham yanıt veya ek dosya içeriği diske yazılmıyor.
- [ ] Kimlik bilgileri yalnızca ortam değişkeni / `.env`'den okunuyor; hiçbir gizli değer commit edilmemiş.
- [ ] Gerçek çalıştırma yalnızca sahibin makinesinde, B-007, B-009 ve B-011 çözüldükten sonra ve Main Agent'ın onayıyla yapılır; sonuçlar gerçek sistem sonucu olarak sentetik sonuçlardan ayrı raporlanır ([docs/TEST_REPORT.md](../../docs/TEST_REPORT.md)).

## Güvenlik kontrol listesi (gerçek çalıştırmadan önce)

- [ ] Betik, commit'i bilinen sürümdür ve mock testleri geçmiştir.
- [ ] Kuru çalıştırma (mock) çıktısı gözden geçirildi: yalnızca izinli çağrılar görülüyor.
- [ ] Kimlik bilgileri sahibin makinesinde ortam değişkeni / `.env` olarak girildi; hiçbir yere yapıştırılmadı.
- [ ] Ana hesap anahtarı kullanılıyor (B-007).
- [ ] Hız ve üst sınırlar muhafazakâr ayarlandı; ilk çalıştırma küçük örneklemle.
- [ ] Rapor yolu depo ve Vault dışında.
- [ ] Çalıştırma sırasında giriş/CAPTCHA benzeri bir müdahale istenirse iş durur ve Main Agent aracılığıyla sahibe bildirilir (AGENTS §6).
- [ ] Çalıştırma sonrası: raporda içerik/kimlik/URL/token olmadığı kontrol edildi, sonra Main Agent'a iletildi.
