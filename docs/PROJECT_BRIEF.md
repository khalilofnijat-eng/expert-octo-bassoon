# PROJECT_BRIEF — Hedef, kapsam, başarı ölçütleri

Kısa özettir; ayrıntı ve bağlayıcı metin: [OWNER_REQUEST_2026-09-27.md](OWNER_REQUEST_2026-09-27.md). Kararlar: [DECISIONS.md](DECISIONS.md).

## Hedef

Avito'da otomotiv parçası satan işletme için; Avito hesabına, depo ve muhasebe sistemine bağlı, 7/24 çalışabilen, müşteriyi doğru ürün seçiminden siparişe taşıyan, ölçülebilir biçimde gelişen ve kaldığı yerden devam edebilen bir müşteri asistanı. Sahiple Türkçe; müşteriyle müşterinin dilinde, Rusça öncelikli.

## Kapsam

- Avito geçmiş konuşmalarının salt okunur, kaldığı yerden devam eden, tekrarsız aktarımı ve analizi (talep §3–4).
- Depo/muhasebe sisteminin keşfi; önce salt okunur bağlantı; ürün modeli ve ilan–depo eşleştirmesi (§5).
- Mesaj ve ilanı anlayan, uyumluluk sorularını soran, gerçek stok/fiyat/fotoğrafla numaralı seçenek sunan, sipariş/rezervasyon akışını yürüten asistan; örnek senaryo Mercedes W213 ön tampon (§2, §6, §7).
- Kontrollü öğrenme: öğrenme adayları, onay, sürümlü bilgi tabanı, sabit değerlendirme senaryoları (§8).
- Kalıcı kayıt, Git, Obsidian Vault yerleşimi (§9–10).
- 7/24 işletim tasarımı ve teknik bilgi gerektirmeyen yönetim ekranı (§11–12).

## Şimdilik kapsam dışı

- Fine-tuning (yalnızca ölçülebilir fayda gösterilirse ayrıca değerlendirilir — D-004).
- Sahip onayı olmadan otomatik müşteri mesajı gönderimi (D-006).
- Sahip onayı olmadan dış sistemlere yazma (D-006).

## Bilgi öncelik sırası (D-005)

1. Güncel ve yetkili stok, fiyat ve sipariş sistemleri.
2. Sahibin onayladığı işletme kuralları.
3. Doğrulanmış ürün ve uyumluluk kaynakları.
4. Onaylı bilgi tabanı.
5. Tarihsel konuşma örnekleri.

## Başarı ölçütleri (talep §14)

- [ ] Geçmiş konuşma aktarımı raporlanmış, kesintiden devam ve tekrar önleme doğrulanmış.
- [ ] Bilgi tabanındaki cevaplar kaynaklarına bağlanabiliyor.
- [ ] Gerçek depo bağlantısı veya kalan erişim engeli açıkça gösterilmiş.
- [ ] Güncel stok ve fiyat doğrulanmadan kesin satış vaadi verilmiyor.
- [ ] Mercedes W213 örneği, fotoğraf ve fiyatlarla uçtan uca test edilmiş.
- [ ] Uygun olmayan veya belirsiz ürünler kesin uyumlu diye sunulmuyor.
- [ ] Tekrarlanan mesaj, eşzamanlı talep, son ürün, bağlantı kesintisi ve insan müdahalesi test edilmiş.
- [ ] Sipariş ve mesaj tekrarlarını önleyen mekanizmalar doğrulanmış.
- [ ] Öğrenme adayları onay ve sürüm yönetiminden geçiyor.
- [ ] Yeni oturum mevcut kayıtlardan işi sürdürebiliyor.
- [ ] Acil durdurma, yedekleme ve geri yükleme çalışıyor.
- [ ] Yerel kurulum ve Obsidian düzeni doğrulanmış.
- [ ] Deneme verisiyle başarılı olan testlerle gerçek sistemde yapılan testler ayrı raporlanmış.
- [ ] 7/24 kullanım için gerekli çalışma ortamı, izleme ve kalan sınırlamalar açıkça belirtilmiş.
