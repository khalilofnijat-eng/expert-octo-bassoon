# SKILLS — Önerilen yeniden kullanılabilir skill'ler

Bu dosya, e-ticaret sitesi projesinde tekrar tekrar yapılacak işler için önerilen skill'leri tanımlar. Proje bağlamı: [KICKOFF_PROMPT.md](KICKOFF_PROMPT.md). Giriş kuralları: [CLAUDE.md](CLAUDE.md). Skill'ler Main Agent'ın alt agent'lara verdiği görevlerde kullanılır; hiçbiri sahip onayı, bağımsız inceleme veya kayıt tutma kuralının yerini tutmaz.

Ortak kurallar (her skill için geçerli): bilgi uydurulmaz, her dış olgu kaynağı ve doğrulanma düzeyiyle yazılır; gizli değerler yalnızca ortam değişkeninde durur; sentetik veri işaretlidir; teslim metni "yapılan iş, değişen dosyalar, doğrulama kanıtı, kalan sorunlar, sorular (Main Agent'a), sonraki adım" yapısındadır.

---

## 1. `vin-lookup-research`

**Ne zaman:** VIN ile araç tanıma yolu seçilirken; poisk.vin veya başka bir VIN/katalog hizmetinin şartları ya da yetenekleri değiştiğinde; VIN çıktısını araç modeline eşleme kuralı yazılırken.

**Girdiler:** Hizmetin adı ve sahibin erişim türü (API anahtarı / yalnızca web hesabı — sahipten); resmî belgeler ve kullanım şartları; ortak veri sözleşmesindeki araç alanları.

**Çıktılar:** `docs/INTEGRATIONS.md`'de kaynaklı bir bölüm (entegrasyon yolu, kimlik doğrulama, sınırlar, ücret/kota, gösterme/önbellek/saklama izinleri, döndürülen alanlar); VIN çıktısı → `make`, `model`, `chassis_code`, yıl, `facelift`, donanım koşulları eşleme tablosu; entegrasyon kararı önerisi veya `BLOCKERS.md` kaydı.

**Adımlar:**
1. Resmî API veya ortaklık/entegrasyon programı var mı araştır; yalnızca resmî kaynakları olgu say, diğerlerini "ikincil kaynak" diye işaretle. Hizmetin kendisi API sunmuyorsa lisanslı alternatifleri de aynı ölçütlerle karşılaştır (başlangıç listesi ve güven etiketleri: [KICKOFF_PROMPT.md](KICKOFF_PROMPT.md) bölüm 2.1).
2. Kullanım şartlarını oku: otomatik erişim, sonuçları üçüncü kişilere gösterme, önbellek ve saklama.
3. Yalnızca web arayüzü varsa **dur**: otomasyon önerisini Main Agent'a soru olarak ilet; sahip onayı olmadan tarayıcı otomasyonu veya scraping kurma.
4. API varsa, kimlik bilgisi ortam değişkeninde olacak şekilde sunucu tarafı ince bir istemci ve sentetik bir sahte (mock) tasarla; istek sınırı ve önbellek ekle.
5. Eşleme tablosunu yaz; eşlenemeyen alanlar "müşteriye sorulacak" olarak işaretlensin.
6. Elle araç seçimi yedek yolunun aynı araç modeline düştüğünü doğrula.

**Kabul kontrolleri:** Her olgunun kaynağı var; kimlik bilgisi kodda, logda veya tarayıcıya giden yanıtta yok; VIN çözümü tek başına `verified` uyumluluk üretmiyor (test); geçersiz VIN (17 karakter değil, I/O/Q içeren) sunucuya gitmeden reddediliyor; hizmet kapalıyken elle seçim çalışıyor.

## 2. `catalog-data-contract`

**Ne zaman:** Ürün, araç, uyumluluk, stok, fiyat veya fotoğraf alanı eklenirken/değiştirilirken; Avito asistanı projesiyle uyum kontrol edilirken; yeni bir stok adaptörü yazılırken.

**Girdiler:** Avito projesindeki referanslar (`docs/ARCHITECTURE.md` §5, `app/catalog/types.py`, `app/catalog/evidence.py`, `app/inventory/port.py`); bu projenin sözleşme dosyaları (OpenAPI/JSON Schema veya paylaşılan paket); önerilen değişiklik.

**Çıktılar:** Güncellenmiş, versiyonlu sözleşme; iki proje arasındaki fark tablosu; sözleşme testleri; gerekiyorsa `docs/DECISIONS.md` için karar önerisi.

**Adımlar:**
1. Avito projesindeki güncel tanımları oku (bu dosyadaki özet değil, depodaki kod geçerlidir).
2. Değişikliği şu değişmezlere karşı kontrol et: SKU + `oem_numbers`; `verified` yalnızca `oem_catalog` / `manufacturer_doc` / `owner_confirmed` kanıtı, dolu referans ve doğrulama zamanıyla; kanıt olmayan türler asla doğrulamaz; her olguda `source`, `data_origin`, `fetched_at`, `verified_at`; okuma durumları `fresh` / `stale` / `unavailable` / `not_found`; fiyat tamsayı `amount_minor` + ISO 4217 `currency`; fotoğraf tek bir stok kaydına bağlı; sentetik SKU `SYN-` önekli.
3. Uyumsuz bir değişiklik gerekiyorsa sözleşme sürümünü artır ve Avito projesi için geçiş notu yaz.
4. Sözleşme testlerini sentetik adaptör üzerinde çalıştır.

**Kabul kontrolleri:** Sözleşme testleri geçiyor; stok kaynağı `down` veya veri eskiyken site "mevcut" demiyor ve kesin fiyat göstermiyor (test); kanıtsız kayıt `verified` görünmüyor (test); üretim modunda sentetik kayıt reddediliyor (test); fark tablosu güncel.

## 3. `visual-model-asset-pipeline`

**Ne zaman:** Görsel araç modeli için yeni bir kasa tipi (pilot: Mercedes-Benz W213) hazırlanırken; bölge/parça eşlemesi değiştirilirken; 2D/3D yaklaşımı yeniden değerlendirilirken.

**Girdiler:** Kasa tipi ve varyantları (makyaj öncesi/sonrası, donanım farkları); onaylı teknoloji kararı; `part_type` sınıflandırması; varlık kaynakları ve lisans belgeleri.

**Çıktılar:** Optimize edilmiş varlıklar (SVG katmanları veya düşük poligonlu model + sıkıştırılmış dokular); bölge/grup/parça kimliği → `part_type` eşleme dosyası; `docs/ASSETS.md` (veya eşdeğeri) içinde her varlığın kaynağı, yazarı ve lisansı; boyut ve performans ölçümleri.

**Adımlar:**
1. Varlığın kaynağını belirle: kendi çizimimiz/modelimiz veya belgeli lisans. Üretici EPC çizimleri, katalog görselleri ve lisansı belirsiz hazır modeller kullanılmaz.
2. Bölgeleri ve montaj gruplarını tanımla; her tıklanabilir öğeye kalıcı bir kimlik ver.
3. Kimlikleri `part_type`'a eşle; eşlenemeyen öğeyi işaretle.
4. Varlığı optimize et ve bütçeye karşı ölç (dosya boyutu, orta segment mobilde yanıt süresi/kare hızı).
5. Klavye ve ekran okuyucu için liste alternatifini aynı eşleme dosyasından üret.
6. Stokta ürünü olmayan grupların görselde nasıl gösterildiğini kontrol et.

**Kabul kontrolleri:** Lisans kaydı olmayan varlık yok; tüm tıklanabilir öğeler eşli veya açıkça "eşlenmedi" işaretli; bütçe aşılmıyor; görsel model uyumluluk kararı vermiyor (uyumluluk yalnızca katalog verisinden geliyor); liste alternatifi aynı parçalara ulaşıyor.

## 4. `design-system-and-ui-review`

**Ne zaman:** Yeni bir ekran veya bileşen tasarlanırken; prototip sahibe sunulmadan önce; üretime alınmadan önce.

**Girdiler:** `docs/DESIGN_SYSTEM.md`; prototip veya çalışan sayfa bağlantısı; hedef cihaz profilleri; ilgili kullanıcı akışı.

**Çıktılar:** Tasarım sistemi güncellemesi (token'lar, bileşenler, durum renkleri, uyumluluk ve stok rozetleri); mobil ve masaüstü ekran görüntüleri; inceleme bulguları (dosya/ekran kanıtı, önem derecesi, önerilen düzeltme).

**Adımlar:**
1. Bileşeni tasarım sistemi token'larıyla kur; yeni renk/boşluk değeri gerekiyorsa önce sisteme ekle.
2. Mobil önce: küçük ekranda akışı baştan sona dene (araç seçimi → parça → sepet → ödeme).
3. Erişilebilirlik: kontrast, odak sırası, klavye kullanımı, ekran okuyucu etiketleri, dokunma hedefi boyutları (hedef WCAG 2.2 AA).
4. Metinler: Rusça, net, uyumluluk ve stok durumunu abartmayan ifadeler; `needs_verification` durumunda müşteriye eksik bilgiyi söyleyen metin.
5. Bağımsız inceleme: ekranı tasarlamayan bir agent bulguları çıkarır.

**Kabul kontrolleri:** Otomatik erişilebilirlik denetiminde kritik bulgu yok ve elle klavye testi geçti; uyumluluk/stok rozetleri tasarım sistemiyle tutarlı; ekran görüntüleri teslimde; sahip onayı prototip aşamasında alındı.

## 5. `checkout-and-compliance-check`

**Ne zaman:** Sepet, sipariş, ödeme, ek ücret, fatura, çek, iade veya kişisel veri toplayan bir form değiştiğinde; yeni ödeme sağlayıcısı eklendiğinde; yayına almadan önce.

**Girdiler:** Ödeme yöntemleri (nakit, СБП/QR, karta havale, şirketler için banka havalesi +%10); `docs/COMPLIANCE.md`; sahibin yasal biçimi ve vergi rejimi (bilinmiyorsa engel); seçilen sağlayıcının test ortamı.

**Çıktılar:** Test edilmiş akış; hesap testleri; uyum kontrol listesi sonuçları; `docs/COMPLIANCE.md` güncellemesi; bağımsız inceleme bulguları.

**Adımlar:**
1. Tutarları tamsayı kopekle hesapla; +%10 ek ücret yalnızca şirket alıcının banka havalesinde, ayrı satırda, belgelenmiş yuvarlama kuralıyla; ek ücretin tabanı sahibin kararına göre.
2. Siparişte stok ve fiyatı yeniden kontrol et; son ürünün iki siparişe ayrılmasını önle; tekrarlanan gönderimde (çift tıklama, ağ tekrarı) tek sipariş oluşsun (idempotency anahtarı).
3. Sipariş durumu ile ödeme durumunu ayrı tut; ödeme sağlayıcısından doğrulanmadan "ödendi" deme.
4. Kontrol listesi: 54-FZ çek akışı (her ödeme yöntemi için), 152-FZ (rıza, gizlilik politikası, veri yerelleştirme, yalnızca gerekli verinin toplanması), mesafeli satış bilgilendirmeleri ve iade koşulları, оферта metni. Her madde için kaynak ve sahip kararı kaydı.
5. Bağımsız inceleme iste.

**Kabul kontrolleri:** +%10 ek ücret yalnızca şirket alıcının banka havalesinde oluşuyor; tüketiciye açık yöntemlerde (kart, QR/СБП, nakit, karta havale) ek ücret satırı oluşmadığını kanıtlayan test var (bkz. [KICKOFF_PROMPT.md](KICKOFF_PROMPT.md) bölüm 3); ek ücret sınır değer testleri (0, 1 kopek, büyük tutarlar, çok satırlı sepet) geçiyor; eşzamanlı son ürün testi geçiyor; idempotency testi geçiyor; kontrol listesindeki her madde "karşılandı / sahip kararı bekliyor (BLOCKERS kimliği)" durumunda; hiçbir ödeme gizli değeri kodda veya logda yok.

## 6. `performance-and-seo-audit`

**Ne zaman:** Her aşamanın sonunda; büyük bir sayfa, kütüphane veya görsel model değişikliğinden sonra; yayına almadan önce.

**Girdiler:** Performans bütçeleri (`docs/DESIGN_SYSTEM.md` veya `docs/PLAN.md`); denetlenecek URL'ler (ana sayfa, katalog, parça sayfası, görsel model, sepet); hedef cihaz profili.

**Çıktılar:** Ölçüm raporu (Lighthouse/Web Vitals, mobil profil, önceki ölçümle fark); SEO denetim sonuçları; bütçe aşımı varsa düzeltme görevleri önerisi.

**Adımlar:**
1. Mobil profil ve yavaş ağ koşuluyla LCP, INP, CLS ve JavaScript/varlık boyutlarını ölç; ölçümü aynı koşullarla tekrarla.
2. Görsel modelin yalnızca gerektiğinde yüklendiğini doğrula.
3. SEO: sunucu tarafı içerik, başlık/açıklama, canonical, schema.org Product/Offer doğrulaması, site haritası, robots, Rusça içerik, kırık bağlantılar.
4. Stok veya fiyat "bilinmiyor" iken yapılandırılmış verinin yanlış bir teklif (Offer) iddiası yayınlamadığını kontrol et.

**Kabul kontrolleri:** Bütçeler karşılanıyor veya aşım gerekçesiyle Main Agent'a raporlanmış; yapılandırılmış veri doğrulayıcıda hatasız; site haritasındaki tüm URL'ler 200 dönüyor; sonuçlar `docs/TEST_REPORT.md`'de tarih ve koşullarıyla.

## 7. `independent-review`

**Ne zaman:** Kritik bir bileşen tamamlandığında (ödeme, ek ücret, uyumluluk gösterimi, kişisel veri, yönetim paneli yetkilendirmesi, VIN entegrasyonu, sözleşme değişikliği) ve Main Agent kabul kararından önce.

**Girdiler:** İncelenecek commit/dal ve dosyalar; görevin brief'i ve kabul ölçütleri; ilgili kararlar.

**Çıktılar:** Salt okunur inceleme raporu (metin): her bulgu için dosya/satır kanıtı, önem derecesi (kritik/yüksek/orta/düşük), önerilen düzeltme; kabul ölçütlerinin tek tek karşılanıp karşılanmadığı.

**Adımlar:**
1. İnceleyen agent'ın işi üretmemiş olduğunu doğrula.
2. Brief'teki kabul ölçütlerini tek tek kanıtla kontrol et; testleri kendin çalıştır.
3. Güvenlik (yetkilendirme, girdi doğrulama, gizli değer sızıntısı), doğruluk (tutarlar, durum geçişleri, eşzamanlılık) ve sahip kurallarını (kanıtsız uyumluluk yok, bayat stokta iddia yok, sentetik veri işaretli, Avito kuralları) kontrol et.
4. Dosya değiştirme; düzeltmeler ayrı bir görevle yapılır.

**Kabul kontrolleri:** Her bulgu kanıtlı; kabul ölçütleri tablosu eksiksiz; "sorun yok" sonucu, hangi kontrollerin yapıldığını listeliyor.

---

## Bu önerileri `.claude/skills/` dosyalarına dönüştürme

Yeni oturumda Main Agent, bir alt agent'a şu işi verebilir:

1. Her skill için `.claude/skills/<name>/SKILL.md` oluştur (`<name>` yukarıdaki ad, ör. `.claude/skills/catalog-data-contract/SKILL.md`).
2. Dosyanın başına YAML ön bilgisi ekle: `name` (klasör adıyla aynı) ve `description` (skill'in ne yaptığı ve **ne zaman** kullanılacağı; Claude skill'i bu açıklamaya bakarak seçer).
3. Gövdeye bu dosyadaki girdiler, çıktılar, adımlar ve kabul kontrollerini taşı; uzun referans içeriği (kontrol listeleri, eşleme şablonları) aynı klasörde ayrı dosyalara koy ve gövdeden bağla.
4. Proje özelindeki gerçek değerleri (sözleşme dosya yolları, bütçeler, komutlar) aşamalar ilerledikçe doldur; bilinmeyenleri uydurma, "BİLİNMİYOR" bırak.
5. Skill'leri küçük bir deneme göreviyle sına ve sonucu `docs/TEST_REPORT.md`'ye yaz; değişiklikleri Dokümantasyon agent'ı commit etsin.
