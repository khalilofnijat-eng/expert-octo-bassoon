# NOTES — İşletme ve uygulama notları

Yalnızca kaynağı belirtilmiş notlar yazılır. Kararlar [DECISIONS.md](DECISIONS.md)'de, engeller [../BLOCKERS.md](../BLOCKERS.md)'de, entegrasyon yetenekleri [INTEGRATIONS.md](INTEGRATIONS.md)'de tutulur.

## İşletme notları

- İşletme Avito'da otomotiv parçası satıyor. — kaynak: [OWNER_REQUEST_2026-09-27.md](OWNER_REQUEST_2026-09-27.md) §2
- Sahiple iletişim Türkçe; müşterilerle müşterinin dilinde, Rusça konuşmalar özellikle desteklenecek. — kaynak: OWNER_REQUEST §2
- Örnek satış senaryosu: Mercedes W213 ön tampon + uyumlu ızgara seçimi. — kaynak: OWNER_REQUEST §6
- Ödeme yöntemleri: nakit, QR/СБП, karta havale; şirketlere banka havalesi (+%10 yalnızca B2B). — kaynak: sahip cevabı 2026-09-27; karar [DECISIONS.md](DECISIONS.md) D-039
- Hukuki biçim: ИП. Avito doğrulama rozeti durumu: BİLİNMİYOR. — kaynak: sahip cevabı 2026-09-27 (B-005)
- Avito Доставка açılacak; müşteriler Avito üzerinden de satın alabilecek. — kaynak: sahip cevabı 2026-09-27 (B-005)
- Sahibin poisk.vin'de yalnızca kendisinin kullandığı tek oturumluk bir paketi var; API erişimi için poisk.vin'e yazacak. — kaynak: sahip cevabı 2026-09-27; engel [../BLOCKERS.md](../BLOCKERS.md) B-015
- Web sitesi ayrı bir projedir (D-041).
- İndirim, teslimat, rezervasyon, iade/garanti ve insana devir kuralları: BİLİNMİYOR — bkz. [../BLOCKERS.md](../BLOCKERS.md) B-005.
- Depo/muhasebe yazılımı ve ürün fotoğraflarının yeri: BİLİNMİYOR — bkz. B-002.

## Avito platform notları

Kaynak: T-002 teslim metni (Main Agent kabul etti; metin repoda yok — bkz. B-012). Güven etiketleri: [INTEGRATIONS.md](INTEGRATIONS.md) başındaki tablo.

- "Товары" sohbetlerinde iletişim bilgisi (telefon, e-posta, sosyal ağ kullanıcı adı) göndermek ve istemek yasak (22 Mayıs 2024'ten beri; belgeyle doğrulanmış profesyonel profiller hariç); ihlal hesabın engellenmesine yol açabiliyor. → Giden mesajlar için bu bilgileri engelleyen bir çıktı filtresi gerekir. — ikincil kaynak
- Platform dışı ödeme veya anlaşma önermemek entegratörlerin tavsiyesi; resmî kural metni doğrulanamadı. → Çıktı filtresi bu önerileri de engellemeli. — ikincil kaynak
- Avito'nun yerleşik "Автоответы" (otomatik yanıt) özelliği satıcı yaklaşık 5 dakika çevrimdışı olduğunda çalışıyor; asistanla birlikte çalışırsa müşteriye çift yanıt gidebilir, kapatılmalı veya asistanla koordine edilmeli. — ikincil kaynak (otomatik yanıtların sistem mesajı olarak görünmesi: [INTEGRATIONS.md](INTEGRATIONS.md) §3.2)
- Anında gönderilen, hep aynı metinli, spam benzeri yanıtların yaptırıma yol açtığı iddia ediliyor. AI asistan kullanımını yasaklayan veya ifşa zorunluluğu getiren bir kural bulunamadı (doğrulanamadı). — ikincil kaynak
- API'den gelen tasarım kısıtları (metin uzunluk sınırı → uzun cevap bölünür; silme penceresi → hatalı gönderimi geri alma bu süreyle sınırlı; okuma sohbeti okundu yapmaz, `chatRead` ayrı çağrı): değerler ve etiketleri [INTEGRATIONS.md](INTEGRATIONS.md) §3.1'de.

### T-037 bulguları (meşru alternatifler araştırması)

Kaynak: T-037 teslim metni (Main Agent kabul etti; metin repoda yok — bkz. B-012). Hepsi **ikincil kaynak** ya da **arama özeti düzeyinde**; hiçbiri Avito'nun resmî metniyle doğrulanmadı. Kararlar: D-039, D-040.

- "Товары" sohbetlerinde iletişim bilgisi 22.05.2024'ten beri yasak. Belge veya rekvizitlerle doğrulanmış profesyonel profiller için bir istisna var, ama kapsamı belirsiz → Avito desteğinden **yazılı teyit** gerekir. — ikincil kaynak
- Avito ilan görsellerinde OCR ile görsel moderasyonu yapıyor (kaynak: Avito'nun teknoloji blogu). Sohbet görsellerinde yapılıp yapılmadığı doğrulanmadı. Fotoğraflar yüzünden hesap engeli bildirilmiş. — ikincil kaynak
- Bazı kategorilerde çevrim içi ödeme zorunlu; 2026 kaynaklarına göre oto parçalar da dahil olabilir (zayıf kanıt). — arama özeti düzeyi
- Tüketiciden kart/QR/СБП ödemesi için ek ücret almak yasak (ЗоЗПП md. 16.1 p.4, Rospotrebnadzor). Bu yüzden sahibin +%10'u yalnızca B2B banka havalesine uygulanır; muhasebeci teyit etmeli. — ikincil kaynak
- poisk.vin: herkese açık API bulunamadı. Resmî API'si olan alternatifler: Laximo, Parts-Catalogs, ACAT. — arama özeti düzeyi

## Ürün ve uyumluluk notları

(Henüz kaynaklı not yok.)

## Uygulama notları

- Uygulama iskeleti ve PII maskeleyici T-014 ile eklendi (commit `11694f5`); düzen: [../app/README.md](../app/README.md). Maskeleyiciyle ilgili kararlar: [DECISIONS.md](DECISIONS.md) D-037, D-038.
