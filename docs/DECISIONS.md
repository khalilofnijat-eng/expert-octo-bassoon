# DECISIONS — Kararlar ve kısa gerekçeleri

Kararların **tek kaynağı** bu dosyadır. Durum değerleri: `geçerli` · `değiştirildi (→ D-xxx)` · `iptal`.

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
| D-010 | 2026-09-27 | Teknoloji yığını seçimi, mevcut sistemlerin keşfi (T-001, T-002, T-007, sahip cevapları) sonrasına ertelendi; T-004'te yapılacak. | Sahip talimatı (talep §11: "teknoloji seçimlerini mevcut sistemlerimi keşfettikten sonra yap"). | geçerli |
| D-011 | 2026-09-27 | Üretim Avito kanalı = resmî Messenger API (webhook + periyodik uzlaştırma yoklaması). Tarayıcı otomasyonu birincil kanal değildir; yalnızca API'nin ulaşamadığı kanıtlanan eski geçmiş için, sahibin açık onayıyla, düşük hızda ve bir kereliğine kullanılabilir. | T-002 raporu §4 ve §S6: API resmî olarak CRM entegrasyonu için sunuluyor; webhook'un tekrar deneme/teslim garantisi belgelenmediği için uzlaştırma yoklaması gerekli; tarayıcı otomasyonu kullanım şartlarına aykırılık, hesap engeli, CAPTCHA, arayüz kırılganlığı, çerez açığa çıkması ve okundu yan etkisi riskleri taşıyor. Rapor repoda yok ([../BLOCKERS.md](../BLOCKERS.md) B-012). Erişim şartı: B-007. | geçerli |
| D-012 | 2026-09-27 | Geçmiş aktarımı, salt okunur bir derinlik ölçüm betiğiyle (T-010) başlar: yalnızca GET, `chatRead` çağrısı yok. | T-002 raporu §4: geçmişin ne kadar geriye okunabildiği belgelenmemiş; mesaj okumak sohbeti okundu yapmaz ([NOTES.md](NOTES.md)), `chatRead` ise karşı tarafa görünür bir yan etki yaratabilir. Önce ölçüm, sonra tam aktarım. Rapor repoda yok (B-012). | geçerli |
| D-013 | 2026-09-27 | Avito için spec'ten yazılmış kendi ince API istemcimiz kullanılır; topluluk SDK'larına bağımlılık yok. | T-002 raporu §S9: topluluk kütüphaneleri resmî değil; kozandlov SDK'sı AGPL-3.0 lisanslı (kapalı kaynak üründe risk); gereken uç sayısı az (~13 Messenger, 3 Items). Rapor repoda yok (B-012). | geçerli |

## Verilen canlı yetkiler

Sahibin verdiği canlı gönderim / dış sisteme yazma yetkileri burada kayıtlıdır (D-006). Her kayıt: tarih, kapsam (hangi işlem, hangi sistem, hangi sınırlar), dayanak (sahibin onayı), gösterilen test kanıtı.

| Tarih | Kapsam | Dayanak | Test kanıtı |
|---|---|---|---|
| — | Henüz verilmiş canlı yetki yok. | — | — |
