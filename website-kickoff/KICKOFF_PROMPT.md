# Oto parça e-ticaret sitesi — başlangıç talimatı

Sen bu projenin **Main Agent**'ısın. Görevin; otomotiv parçaları (yeni ve çıkma) sattığım işletmem için çok kaliteli bir e-ticaret sitesini araştırmak, tasarlatmak, alt agent'lara kurdurmak, test ettirmek, belgelemek ve gerçek kullanıma hazır hâle getirmektir. Bunu yalnızca plan hazırlamak olarak yorumlama.

Ben işin sahibiyim. Benimle Türkçe konuş. Arayüz ve tasarımın tamamı sana ait; teknik mimariyi, agent rollerini, skill'leri ve geliştirme sırasını sen yöneteceksin. İşletmem hakkında bilmediğin bir şeyi uydurma; gerçekten gerekli bilgileri benden toplu hâlde iste.

Bu site **ayrı bir projedir.** Paralel olarak bir Avito müşteri asistanı projem yürüyor (GitHub: `khalilofnijat-eng/expert-octo-bassoon`, dal `claude/youthful-goldberg-l427nm`). İki proje ileride birleştirilecek; bu yüzden ürün, uyumluluk ve stok verisini baştan uyumlu tasarla (bkz. bölüm 5).

Bu depoda `CLAUDE.md` ve `SKILLS.md` varsa onları kullan. Yoksa aynı içerik yukarıdaki depoda `website-kickoff/` klasöründe; oradan alınmasını sağla (depoya erişim yoksa bunu bana söyle).

---

## 1. Çalışma modeli (Avito projesindekiyle aynı)

1. **Ben yalnızca seninle konuşurum.** Kod yazma, dosya düzenleme, araştırma, test, kurulum ve kayıt tutma işlerini gerçek alt agent'lara yaptır. Senin işin; hedefi anlamak, karar vermek, görev dağıtmak, teslimleri kabul veya red etmek ve bana özet vermektir. Gerçek alt agent desteği yoksa bunu açıkça söyle; tek başına çalışıp alt agent kullanıyormuş gibi davranma.
2. **Her görevin brief'i** amaç, kapsam, bağımlılıklar, dosya sahipliği, beklenen çıktı ve doğrulanabilir kabul ölçütleri içersin. Alt agent'lar bana soru sormaz; sorularını sana iletir.
3. **Bağımsız işler paralel, bağımlı işler sırayla** yürüsün. Aynı dosyaya eşzamanlı, kontrolsüz değişiklik yapılmasın.
4. **Kritik bileşenleri bağımsız bir agent incelesin:** ödeme ve sipariş akışı, fiyat/ek ücret hesabı, uyumluluk gösterimi, kişisel veri işleme, yetkilendirme ve yönetim paneli, VIN entegrasyonu. İnceleyen agent incelediği işi üretmemiş olmalı.
5. **Kalıcı kayıtlar.** Hiçbir kritik bilgi yalnızca sohbette kalmasın. Dokümantasyon agent'ı baştan şu kayıtları kursun ve güncel tutsun: `AGENTS.md`, `CLAUDE.md`, `README.md`, `STATE.md`, `HANDOFF.md`, `TASKS.md`, `BLOCKERS.md`, `CHANGELOG.md`, `docs/PROJECT_BRIEF.md`, `docs/ARCHITECTURE.md`, `docs/PLAN.md`, `docs/DECISIONS.md`, `docs/NOTES.md`, `docs/INTEGRATIONS.md`, `docs/DESIGN_SYSTEM.md`, `docs/COMPLIANCE.md`, `docs/ASSETS.md` (görsel varlıkların kaynağı ve lisansı), `docs/TEST_REPORT.md`, `docs/RUNBOOK.md`, `docs/LESSONS_LEARNED.md`, `sessions/`, `tasks/`. Tek kaynak ilkesi: aynı bilgi iki yerde tekrarlanmaz, bağlantı verilir. Yeni oturum önce `AGENTS.md`, `STATE.md`, `HANDOFF.md`, `TASKS.md`, `BLOCKERS.md` okur ve önceki süreçlerin hâlâ çalıştığını varsaymaz.
6. **Bilgi uydurma.** Bilinmeyen "BİLİNMİYOR" diye yazılır ve `BLOCKERS.md`'deki bir kimliğe bağlanır. Dış hizmetlerin (poisk.vin, ödeme sağlayıcıları, barındırma) yeteneklerini, fiyatlarını ve şartlarını resmî kaynaktan doğrulamadan kesin bilgi gibi yazma; her olgunun kaynağını ve doğrulanma düzeyini belirt.
7. **Soruları toplu sor.** Ortamdan veya araştırmayla öğrenilebilecek şeyi bana sorma. Kalan soruları kısa, numaralı ve gruplanmış bir listeyle ilet.
8. **Gizli bilgiler asla sohbette değil.** Benden şifre, API anahtarı, token veya çerezi sohbete yapıştırmamı isteme. Bunlar yalnızca çalışacak makinenin ortam değişkenlerine veya git'e girmeyen `.env` dosyasına girilir; belgelere yalnızca değişkenin **adı** yazılır.
9. **Depo gizli olsun.** Bu proje için özel (private) bir GitHub deposu kullanılsın. Maliyet, indirim sınırı, tedarikçi bilgisi, müşteri verisi, sipariş kayıtları, veritabanları ve gerçek ürün fotoğrafları git'e girmesin. Depo açık (public) görünüyorsa işletme verisi commit edilmeden önce bana sor.
10. **Sentetik veri açıkça işaretli olsun.** Örnek ürünlerde `SYN-` SKU öneki ve `data_origin = synthetic` kullanılsın; sentetik fotoğraflar "SYNTHETIC" filigranı taşısın; üretim modu sentetik veriyi reddetsin. Örnek veriyle yapılan iş gerçek entegrasyon tamamlanmış gibi sunulmasın. Test raporunda sentetik veri sonuçları ile gerçek veri sonuçları **ayrı** raporlansın.
11. **Küçük, doğrulanabilir aşamalar.** Her aşamanın kabul ölçütü kanıtla (test çıktısı, ekran görüntüsü, Lighthouse raporu, inceleme notu, commit hash'i) kapatılsın.
12. **Önce tasarım, sonra prototip, sonra inceleme, sonra yapım.** Görsel ve etkileşimli her büyük özellik için: tasarım önerisi → tıklanabilir prototip → bağımsız inceleme ve benim onayım → üretim kodu.
13. **Maliyet disiplini.** Gereksiz agent çoğaltma, sonsuz görev döngüsü kurma; ortamın eşzamanlılık ve kullanım sınırlarına uy.
14. **Bana raporlama:** teknik ayrıntı yığını yerine kısa özet ver: ne tamamlandı, hangi kanıtla doğrulandı, ne engelli, sıradaki somut adım ne.

## 2. Ürün vizyonu

Müşteri siteye girer, aracını tanıtır (VIN ile ya da elle seçerek), aracının parçalara ayrılabilen görsel modelini görür, bir parçaya tıklar, o parçanın bu araca uygunluğunu, teknik ayrıntılarını, gerçek fotoğraflarını, fiyatını ve stok durumunu görür, sepete ekler ve satın alır. Aynı zamanda sitede tüm ürünlerim klasik bir katalog olarak da aranabilir ve listelenebilir.

### 2.1 VIN ile araç tanıma (poisk.vin)

poisk.vin'de ücretli bir hesabım var. Önce şunu **araştır**, sonra karar ver:

> **Ön bulgular (Avito projesi, araştırma görevi T-037; yeniden doğrula):**
> - poisk.vin için herkese açık, belgelenmiş bir API bulunamadı *(güven: doğrulanmadı — "unverified")*. Tek ipucu, "Мои доступы" giriş bilgileriyle yapılan bir entegrasyondan söz edilmesi; bağlamı belirsiz *(güven: ikincil kaynak, arama özeti düzeyinde)*.
> - Bu yüzden: poisk.vin'den **yazılı** API/entegrasyon izni iste (talebi ben iletirim, gerekirse sen metnini hazırla); poisk.vin **asla** kazınmaz (scraping yok).
> - Resmî API'si olan lisanslı alternatifler, karşılaştırılmak üzere:
>   - **Laximo** (Laximo.CAT ve Laximo.DOC; GitHub'da SOAP ve REST SDK'ları) *(güven: resmî kaynak, sayfalar gerçekten okundu)*;
>   - **Parts-Catalogs** (REST API ve widget, istek başına ücret) *(güven: ikincil kaynak, arama özeti düzeyinde)*;
>   - **ACAT**, **Tradesoft**, **VINPIN**, **VINOPEN** *(güven: ikincil kaynak, arama özeti düzeyinde)*.
> - TecDoc'un Rusya'daki lisans durumu *(güven: doğrulanmadı)*.
> - Alternatifler için de aynı sorular geçerli: resmî belge, fiyat, kullanım şartları, sonuçların sitede gösterilmesi ve önbelleğe alınması, döndürülen veriler (özellikle OEM parça kataloğu verip vermediği).

- poisk.vin'in resmî bir API'si veya başka bir resmî entegrasyon yolu var mı? Varsa belgeleri, kimlik doğrulama yöntemi, istek sınırları, ücretlendirme/kotası ve kullanım şartları neler?
- Kullanım şartları, sorgu sonuçlarının bir sitede müşterilere gösterilmesine, önbelleğe alınmasına ve saklanmasına izin veriyor mu?
- Bir VIN sorgusu tam olarak hangi verileri döndürüyor: yalnızca araç kimliği (marka, model, kasa kodu, yıl, makyaj, donanım/opsiyon kodları) mı, yoksa OEM parça numaraları ve parça kataloğu da mı?
- **Yalnızca web arayüzü varsa** hiçbir otomasyon (tarayıcı otomasyonu, scraping) kurmadan önce bana sor. Giriş, CAPTCHA veya platformun hız ve güvenlik kontrolleri atlatılmaya çalışılmasın.
- Kimlik bilgileri yalnızca ortam değişkeninde dursun. Sorgular sunucu tarafında yapılsın; anahtar tarayıcıya asla gitmesin. Kötüye kullanıma karşı istek sınırı ve önbellek olsun.
- VIN'i kişisel veriyle ilişkilendirilebilecek bir bilgi olarak ele al: gereksiz yere loglama, siparişle ilişkilendirilecekse saklama süresini tanımla.

Her durumda **elle araç seçimi** yedek yol olarak bulunsun: marka → model → kasa kodu → yıl → makyaj öncesi/sonrası → donanım (ör. donanım paketi, park sensörü sayısı, far yıkama, ön kamera). Seçilen araç "Garajım" gibi kalıcı bir çubukta görünsün ve tüm sayfalarda filtre olarak kullanılsın.

VIN çözümü aracı **tanır**; bir parçanın o araca uyduğunu tek başına kanıtlamaz (bkz. 2.2).

### 2.2 Parçalara ayrılabilen görsel araç modeli

- Araç görseli bölgelere ve montaj gruplarına ayrılsın: ön tampon, ızgara, farlar, sis farları, kaput, çamurluklar, aynalar, kapılar, arka tampon, stoplar vb. Kullanıcı önce bölgeyi, sonra grubu, sonra tek parçayı seçebilsin ("patlatılmış" görünüm).
- Bir parçaya tıklanınca bir **ayrıntı paneli** açılsın (masaüstünde yan panel, mobilde alttan açılan sayfa):
  - SKU ve OEM numaraları,
  - kısa teknik ayrıntılar (malzeme, taraf sol/sağ, bağlantı noktaları, sensör delikleri, uyumlu donanımlar vb. — hangi alanların bulunduğu gerçek veriye göre belirlenir),
  - **bu araç için uyumluluk durumu:** `verified` (doğrulanmış, kanıt türü ile), `needs_verification` (doğrulanması gerekiyor; eksik bilgi varsa müşteriye hangi bilginin eksik olduğu söylenir) veya `incompatible`. **Kanıt olmadan asla "uyar" deme.** Görsel benzerlik, kasa kodunun aynı olması, ilan başlığı, müşterinin beyanı veya bir yapay zekâ çıktısı kanıt değildir.
  - durum (yeni/çıkma) ve kondisyon notları, renk,
  - **o stok kaydına bağlı gerçek fotoğraflar** (başka ürünün veya yapay üretilmiş fotoğraf asla kullanılmaz; fotoğraf yoksa "fotoğraf yok" denir),
  - fiyat ve stok durumu (güncel değilse kesin iddia yok, bkz. 5),
  - "Sepete ekle" ve "Uzmana sor" düğmeleri.
- Bir montaj grubunda stokta ürün yoksa bu görselde anlaşılır biçimde belirtilsin; müşteri boş bir parçaya tıklayıp hayal kırıklığı yaşamasın.
- Görsel model bir **gezinme aracıdır**, uyumluluk kaynağı değildir. Bölge/parça kimlikleri ortak bir parça türü sınıflandırmasına (`part_type`) eşlensin; ürünler bu sınıflandırma ve araç ölçütleriyle katalogdan aranır, uyumluluğu uyumluluk kuralları belirler.
- Erişilebilirlik: görsel modelin klavye ile kullanılabilen ve ekran okuyucuya uygun bir **liste alternatifi** olsun.

**Teknoloji seçimi prototiple yapılsın.** En az iki yaklaşımı küçük prototiplerle karşılaştır:

- A) Katmanlı **2D SVG** patlatılmış diyagramlar (tıklanabilir bölgeler, yakınlaştırma, animasyonlu ayrışma),
- B) **3D** yaklaşım (ör. three.js / react-three-fiber) ve kendi ürettiğimiz düşük poligonlu modeller; gerekirse 2D'ye geri düşme.

Karşılaştırma ölçütleri: orta segment bir Android telefonda performans ve pil, ilk yükleme boyutu, bir kasa tipi için varlık (asset) üretim maliyeti ve süresi, yeni kasa tiplerine genişleme kolaylığı, erişilebilirlik ve **hukuki lisans**. Üreticilerin EPC katalog çizimleri ve hazır 3D araç modelleri genellikle telif hakkıyla korunur; bu yüzden yalnızca **kendi ürettiğimiz veya lisansını belgelediğimiz** varlıklar kullanılsın. Her varlığın kaynağı ve lisansı `docs/ASSETS.md`'ye kaydedilsin. Marka logoları ve ticari marka kullanımını da araştır.

**Pilot:** tek kasa tipiyle başla — **Mercedes-Benz E-Serisi W213** (Avito projesindeki örnek senaryo: W213 ön tampon ve uygun ızgara seçimi). Pilotta varlık üretim hattını (çizim/modelleme → bölge kimlikleri → parça türü eşlemesi → doğrulama) belgele ki sonraki kasa tipleri aynı hattan geçsin.

### 2.3 Katalog, arama ve SEO

- Tüm ürünlerim listelensin: kategori, marka/model/kasa, durum (yeni/çıkma), fiyat ve stok filtreleri.
- Arama: **OEM numarası** (boşluk, tire ve nokta farklarına dayanıklı normalizasyonla), parça adı (Rusça eş anlamlılar ve yaygın yazım farklılıkları) ve araç ile.
- Her parça için arama motoru dostu, sunucu tarafında üretilen bir sayfa: anlamlı URL, başlık ve açıklama, yapılandırılmış veri (schema.org Product/Offer), site haritası, canonical. Rusya pazarında Yandex'i de hedefle (Yandex Webmaster; analitik aracı seçimi 152-FZ açısından değerlendirilsin).
- Ana dil **Rusça**. Başka dil gerekip gerekmediğini bana sor; çok dilli yapı sonradan eklenebilecek şekilde kurulsun.

### 2.4 Tasarım

- Premium, hızlı, **önce mobil** bir tasarım. Tasarım sistemi (renk, tipografi, boşluk, bileşenler, durum renkleri — özellikle uyumluluk ve stok rozetleri) `docs/DESIGN_SYSTEM.md`'de belgelensin.
- Erişilebilirlik hedefi WCAG 2.2 AA.
- Performans bütçeleri baştan tanımlansın ve her aşamada ölçülsün (öneri; ilk aşamada kesinleştir: orta segment mobil cihazda LCP ≤ 2,5 sn, INP ≤ 200 ms, CLS ≤ 0,1; ilk sayfa için JavaScript bütçesi; 3D/görsel model yalnızca gerektiğinde yüklensin).
- Güven unsurları: gerçek fotoğraflar, açık uyumluluk durumu, açık ödeme ve iade koşulları, işletme bilgileri.

### 2.5 Sepet ve ödeme

Sepet → iletişim ve teslimat bilgisi → ödeme yöntemi seçimi → sipariş özeti ve onay. Sipariş ile ödeme ayrı durumlardır; ödeme doğrulanmadan "ödendi", stok doğrulanmadan "ayrıldı" denmez. Ayrıntılar bölüm 3'te.

### 2.6 Yönetim paneli

Ürünler, fotoğraflar (stok kaydına bağlı), fiyatlar, stok, uyumluluk kayıtları ve kanıtları, siparişler ve ödeme durumları. Teknik bilgi gerektirmeyen, sade bir arayüz; güçlü kimlik doğrulama; her değişiklik denetim kaydına (kim, ne zaman, ne) yazılsın. Stok ve fiyatın asıl kaynağı depo sistemim olacaksa panel bunları yalnızca gösterir (bkz. 5).

### 2.7 Yapılmayacaklar (Avito kuralları)

Site kendi başına meşru bir satış kanalıdır. Müşteriler siteye arama motorlarından, doğrudan ziyaretle ve Avito'nun resmî olarak izin verdiği bağlantılar üzerinden gelir. **Avito'dan veri kazıma (scraping) ve Avito sohbetindeki müşterileri platform dışına çekmeye yönelik hiçbir özellik yapılmaz.** Ürün verisi Avito ilanlarından değil, katalog/depo kaynağından gelir. Avito'da hangi bağlantıların izinli olduğu Avito projesinde araştırılıyor; site buna bağımlı olmasın.

## 3. Ödeme ve yasal uyum

Hukuki görüş yazma; bulguları kaynaklarıyla `docs/COMPLIANCE.md`'ye işle, kararı bana bırak. Kaynağı resmî olmayan bulguları öyle işaretle.

**Kabul ettiğim ödeme yöntemleri:**

1. Nakit (нал)
2. QR kod ile ödeme (СБП / QR)
3. Karta havale (перевод на карту)
4. Şirketler için banka havalesi (безнал) — tutara **+%10** ek ücret uygulanır (yalnızca şirket alıcılar, B2B)

> **Dikkat — ek ücret ve tüketici hukuku (T-037 bulgusu; yeniden doğrula):** Bireysel tüketicilerden kartla, QR ile veya СБП ile ödeme için ek ücret almak ЗоЗПП md. 16.1 f.4 uyarınca yasaktır *(güven: resmî Rospotrebnadzor kaynağı, yalnızca arama özeti düzeyinde okundu)*. Bu yüzden:
> - +%10 **yalnızca şirket alıcıların banka havalesine (безнал, B2B)** uygulanır;
> - site tüketicilere kart/QR/СБП için **hiçbir zaman** ek ücret göstermez;
> - bu yorum, benim muhasebecimle **teyit edilecek** madde olarak `docs/COMPLIANCE.md` ve `BLOCKERS.md`'ye yazılır.

Araştırılacaklar:

- Her yöntemin sitede nasıl sunulacağı: çevrim içi mi, teslim/elden teslimde mi, fatura (счёт) ile mi? Kurumsal müşteri için hangi şirket bilgileri (ör. ИНН, КПП, unvan) toplanmalı ve fatura nasıl üretilmeli?
- **+%10 ek ücret** yalnızca şirket alıcı banka havalesini (безнал) seçtiği anda, sepet ve sipariş özetinde ayrı bir satır olarak şeffafça gösterilsin; hesap tamsayı kopek ile yapılsın, yuvarlama kuralı belgelenip test edilsin. Tüketiciye açık hiçbir ödeme yönteminde ek ücret satırı oluşmasın (yukarıdaki dikkat notu). B2B satışta ek ücretin fatura ve çekte nasıl gösterileceğini araştır. Ek ücretin teslimat dâhil toplam tutara mı yoksa yalnızca ürünlere mi uygulanacağını bana sor.
- Çevrim içi ödeme sağlayıcısı seçenekleri (Rusya'da çalışan banka/ödeme aracıları, SBP desteği, komisyonlar, entegrasyon şartları, 54-FZ çek desteği). Hiçbir sağlayıcıyı doğrulamadan önermeyelim; karşılaştırma tablosu hazırla.
- **54-FZ online kasa (онлайн-касса)** yükümlülükleri: çevrim içi satışta, karta havalede, SBP'de, nakit ve elden teslimde çek düzenleme şartları ve bunların sağlayıcı/OFD ile nasıl karşılanacağı.
- **152-FZ kişisel veri:** Rusya'da barındırma (yerelleştirme), açık rıza metinleri, gizlilik politikası, çerez/analitik kullanımı, sınır ötesi aktarım, işletmecinin Roskomnadzor bildirimi gerekip gerekmediği.
- **Mesafeli satışta tüketici hakları:** iade/cayma süreleri ve şartları, çıkma (kullanılmış) parçalar için özel durumlar, satış öncesi zorunlu bilgilendirmeler, kamuya açık teklif (оферта) metni.
- Karta havalenin işletme adına kullanılmasının vergi ve yasal sonuçları (ödeme yöntemi olarak sunulmadan önce).
- İşletmemin yasal biçimi (ИП / ООО / самозанятый) ve vergi rejimi: **bana sor**; ödeme, çek ve KDV/fatura tasarımı buna bağlı.
- Teslimat yöntemleri (elden teslim, kargo şirketleri, şehir içi kurye vb.): **bana sor.**

## 4. Aşamalar ve tamamlanma ölçütleri

Her aşamada sentetik veri ve gerçek veri test sonuçları `docs/TEST_REPORT.md`'de **ayrı** raporlanır. Bir aşama, ölçütleri kanıtla karşılanmadan kapanmaz.

| # | Aşama | Kabul ölçütleri (doğrulanabilir) |
|---|---|---|
| 0 | **Keşif ve kurulum** | Kayıt dosyaları oluşturulmuş ve commit edilmiş; özel depo doğrulanmış; ilk soru listesi bana iletilmiş; poisk.vin, ödeme sağlayıcıları ve uyum konularında kaynaklı araştırma notları `docs/INTEGRATIONS.md` ve `docs/COMPLIANCE.md`'de; Avito projesinin veri sözleşmesi incelenmiş ve farklar listelenmiş. |
| 1 | **Tasarım sistemi ve prototip** | `docs/DESIGN_SYSTEM.md` yazılmış; ana sayfa, katalog, parça sayfası, araç seçimi, görsel model, sepet ve ödeme ekranlarının tıklanabilir prototipi var; mobil ve masaüstü ekran görüntüleri; bağımsız UI/erişilebilirlik incelemesi yapılmış; benim onayım alınmış. |
| 2 | **Katalog ve araç seçimi (VIN)** | Ortak veri sözleşmesi (bölüm 5) belgelenmiş ve sözleşme testleri geçiyor; sentetik katalogla OEM normalizasyonu, parça adı ve araç araması testli; elle araç seçimi çalışıyor; VIN yolu yalnızca doğrulanmış resmî bir entegrasyonla veya benim onayladığım yöntemle bağlanmış, değilse engel olarak kayıtlı; stok kaynağı kapalı/eski olduğunda "mevcut" iddiası olmadığını gösteren test var. |
| 3 | **Görsel model pilotu (W213)** | 2D ve 3D prototip karşılaştırması ölçümleriyle (boyut, orta segment mobilde kare hızı/yanıt süresi, varlık maliyeti, lisans durumu) raporlanmış ve karar `docs/DECISIONS.md`'de; W213 için tüm bölgeler tıklanabilir ve `part_type`'a eşli; ayrıntı panelinde uyumluluk durumu kanıt türüyle gösteriliyor; kanıtsız "uyar" iddiası olmadığını gösteren testler; tüm varlıkların kaynağı ve lisansı kayıtlı; klavye ile kullanılabilen liste alternatifi var. |
| 4 | **Sepet ve ödeme akışı** | Dört ödeme yöntemi akışta; +%10 ek ücret yalnızca şirket alıcının banka havalesinde, ayrı satırda ve tamsayı kopekle doğru (sınır değer testleri); tüketiciye kart/QR/СБП/nakit için ek ücret gösterilmediğini kanıtlayan test; siparişte stok ve fiyat yeniden kontrol ediliyor; aynı son ürünün iki siparişe (ve ileride Avito'daki satışa) birden ayrılmasını önleyen yöntem testli; tekrarlanan gönderimde çift sipariş oluşmuyor (idempotency); sipariş ve ödeme durumları ayrı; bağımsız inceleme yapılmış. |
| 5 | **Yönetim paneli** | Ürün, fotoğraf, fiyat, stok, uyumluluk ve sipariş yönetimi; fotoğraf yalnızca stok kaydına bağlanabiliyor; yetkilendirme ve denetim kaydı testli; bağımsız güvenlik incelemesi. |
| 6 | **Yasal uyum** | `docs/COMPLIANCE.md` maddeleri tamamlanmış ve benim kararlarım kayıtlı; gizlilik politikası, rıza metinleri, оферта ve iade koşulları sitede; 54-FZ çek akışı seçilen sağlayıcının test ortamında doğrulanmış; barındırma yerelleştirme kararı uygulanmış. |
| 7 | **Performans ve SEO** | Performans bütçeleri ölçülmüş (Lighthouse/Web Vitals raporları, mobil profil); yapılandırılmış veri doğrulanmış; site haritası, robots, canonical ve meta etiketler denetlenmiş; erişilebilirlik denetimi (otomatik + elle klavye/ekran okuyucu kontrolü) geçmiş. |
| 8 | **Yayına alma** | Üretim ortamı, yedekleme ve geri yükleme testli; izleme ve uyarılar çalışıyor; `docs/RUNBOOK.md` yazılmış; sentetik veri üretimde yok (otomatik kontrol); gerçek veriyle uçtan uca sipariş denemesi (W213 ön tampon + ızgara senaryosu) yapılmış ve sonuçları sentetik testlerden ayrı raporlanmış; kalan sınırlamalar açıkça listelenmiş. |

## 5. Avito asistanıyla ileride birleşme

Veri modelini Avito projesiyle uyumlu tut. Referanslar (depo `khalilofnijat-eng/expert-octo-bassoon`, dal `claude/youthful-goldberg-l427nm`): `docs/ARCHITECTURE.md` §5 (veri modeli), `app/catalog/types.py`, `app/catalog/evidence.py`, `app/catalog/fitment.py`, `app/inventory/port.py`. Önce bu dosyaları okut; aşağıdaki özet ile çelişirse depodaki güncel kod geçerlidir.

- **Ürün kimliği:** SKU ve OEM numaraları (`oem_numbers`, kaynakta yazıldığı gibi saklanır; arama normalleştirir). Ürün alanları: `sku`, `title`, `part_type`, `brand`, `condition` (`new`/`used`), `color`, `condition_notes`, `set_kind` (`single`/`virtual_set`/`stocked_set`). Setler ve set bileşenleri (eksik bileşen bilgisi dâhil) desteklenir.
- **Araç uygulanabilirliği:** `make`, `model`, `chassis_code`, `year_from`, `year_to`, `facelift`; donanım koşulları `trim_line`, `parktronic_sensors`, `headlamp_washer`, `front_camera`. VIN çözümünün çıktısı bu alanlara eşlenir; eşlenemeyen alan uydurulmaz, müşteriye sorulur.
- **Uyumluluk durumları ve kanıt türleri:** durumlar `verified` / `needs_verification` / `incompatible`. `verified` yalnızca `oem_catalog`, `manufacturer_doc` veya `owner_confirmed` kanıtıyla, dolu bir kanıt referansı ve doğrulama zamanıyla olur. `visual_similarity`, `customer_statement`, `llm_output`, `listing_title`, `body_code_only` asla kanıt değildir. `synthetic_fixture` yalnızca test modunda ve sentetik kayıtta geçerlidir; üretimde reddedilir.
- **Kaynak ve tazelik:** her olgu `source`, `data_origin`, `fetched_at`, `verified_at` taşır. Okumalar `fresh` / `stale` / `unavailable` / `not_found` durumu döndürür. Stok kaynağı kapalıysa veya veri eskiyse **stok iddiası yok** ("наличие уточняется"); fiyat güncel değilse **kesin fiyat yok**. Bu kural tek bir yerde uygulanır.
- **Fiyatlar** tamsayı küçük birimle (`amount_minor`, RUB için kopek) ve ISO 4217 `currency` ile tutulur; toplamlar ve ek ücretler kodla hesaplanır, kayan nokta kullanılmaz.
- **Fotoğraflar** tek bir stok kaydına bağlı referanslardır (`photo_key`, `sku`, `stock_ref`, sıra).
- **Stok portu:** depo/muhasebe yazılımım henüz belirlenmedi. Bu yüzden salt okunur bir stok arayüzü (port) ve açıkça etiketli **sentetik bir adaptör** kullanılsın; gerçek adaptör, yazılım belirlendikten sonra yazılır. Port sağlık durumu (`up`/`degraded`/`down`) raporlar.
- **Ortak sözleşme önerisi hazırla:** iki seçeneği karşılaştır — (a) versiyonlu bir API sözleşmesi (OpenAPI/JSON Schema) ve sözleşme testleri, (b) iki projenin kullandığı paylaşılan bir paket/şema. Avito projesinin çekirdek yığını Python 3.11, FastAPI, PostgreSQL 16; birleşmeyi kolaylaştırıp kolaylaştırmadığını yığın kararında değerlendir.
- **Avito'da çevrim içi ödeme (birleşme konusu, sitenin kapsamı değil):** Avito'da bazı kategorilerde çevrim içi ödemenin zorunlu hâle geldiği ve 2026 kaynaklarına göre oto parçaların da bunlara dâhil olduğu bildiriliyor *(güven: zayıf ikincil kaynak)*. Doğruysa Avito'dan gelen alıcılar için nakit ve karta havale akışları etkilenir; birleşme tasarımında dikkate alınsın ve Avito projesiyle birlikte doğrulansın.
- **Katalogun tek doğruluk kaynağı** konusunda bir öneri ve karar kaydı hazırla: stok ve fiyatın asıl kaynağı depo sistemi mi, yoksa ortak bir katalog veritabanı mı; site içeriği (açıklamalar, SEO metinleri, görsel model eşlemeleri) nerede tutulur; iki kanal aynı çıkma parçayı aynı anda satarsa çift satış nasıl önlenir. Ortak stok ve rezervasyon kurulana kadar sitedeki siparişler "sahip onayı bekliyor" durumunda başlasın ve müşteriye onaydan önce "ayrıldı" denmesin.

## 6. Benden istenecek ilk bilgiler (toplu sor)

1. Alan adı var mı, hangisi? Barındırma tercihi (Rusya'da sunucu vb.) ve mevcut hesaplar.
2. Yasal biçim (ИП / ООО / самозанятый) ve vergi rejimi.
3. poisk.vin erişim türü: API anahtarı mı, yalnızca web hesabı mı? Paket, sorgu kotası ve sözleşme şartları. poisk.vin'den yazılı API/entegrasyon izni istemeyi kabul ediyor musunuz; olmazsa lisanslı bir alternatif (ör. Laximo) için ayrı ücret ödemeye hazır mısınız?
4. Marka: işletme adı, logo, renkler, varsa kurumsal kimlik.
5. Öncelikli markalar/modeller/kasa tipleri (W213'ten sonra hangileri).
6. Yaklaşık ürün (SKU) sayısı ve yeni/çıkma oranı.
7. Ürün fotoğrafları şu an nerede ve nasıl adlandırılıyor?
8. Teslimat yöntemleri, bölgeler ve elden teslim noktası.
9. İade ve garanti kuralları (yeni ve çıkma parça için ayrı ayrı).
10. Ödeme: +%10 ek ücretin yalnızca şirketlere banka havalesinde uygulanacağını muhasebecinizle teyit eder misiniz; ek ücretin tabanı (ürün mü, toplam mı), çevrim içi ödeme sağlayıcısı kullanmak istiyor muyum, karta havale kişisel karta mı işletme hesabına mı (kart/hesap numarasını sohbete değil, güvenli yapılandırmaya gireceğim).
11. Rusça dışında dil gerekiyor mu?
12. Bütçe: barındırma, ödeme sağlayıcısı komisyonu, ücretli tasarım/3D varlık ve lisanslar için aylık/tek seferlik sınır.

## 7. Şimdi nasıl başlayacaksın?

1. Main Agent rolünü benimse ve gerçek alt agent desteğini doğrula.
2. Dokümantasyon agent'ına kayıt düzenini kurdur (bölüm 1.5); bu talimatı değiştirilmez sahip talebi olarak `docs/OWNER_REQUEST_<tarih>.md` dosyasına kelimesi kelimesine kaydettir.
3. Paralel olarak araştırma görevleri başlat: poisk.vin entegrasyon yolları ve şartları; ödeme sağlayıcıları ve 54-FZ; 152-FZ ve mesafeli satış kuralları; görsel model varlıkları ve lisanslama; Avito projesinin veri sözleşmesinin incelenmesi.
4. Bölüm 6'daki soruları bana tek mesajda ilet.
5. Cevapları beklerken engellenmemiş işleri (tasarım sistemi, prototipler, sentetik katalog, sözleşme taslağı) ilerlet; sentetik veriyle yapılan işi açıkça işaretle.

Hedef: gerçek ürünlerimi doğru uyumluluk bilgisiyle gösteren, müşteriyi aracından doğru parçaya ve güvenli bir siparişe taşıyan, hızlı ve güzel, yasal olarak uyumlu ve ileride Avito asistanıyla sorunsuz birleşebilen bir e-ticaret sitesi.
