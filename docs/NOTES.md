# NOTES — İşletme ve uygulama notları

Yalnızca kaynağı belirtilmiş notlar yazılır. Kararlar [DECISIONS.md](DECISIONS.md)'de, engeller [../BLOCKERS.md](../BLOCKERS.md)'de, entegrasyon yetenekleri [INTEGRATIONS.md](INTEGRATIONS.md)'de tutulur.

## İşletme notları

- İşletme Avito'da otomotiv parçası satıyor. — kaynak: [OWNER_REQUEST_2026-09-27.md](OWNER_REQUEST_2026-09-27.md) §2
- Sahiple iletişim Türkçe; müşterilerle müşterinin dilinde, Rusça konuşmalar özellikle desteklenecek. — kaynak: OWNER_REQUEST §2
- Örnek satış senaryosu: Mercedes W213 ön tampon + uyumlu ızgara seçimi. — kaynak: OWNER_REQUEST §6
- Fiyat, indirim, teslimat, ödeme, rezervasyon, iade/garanti ve insana devir kuralları: BİLİNMİYOR — bkz. [../BLOCKERS.md](../BLOCKERS.md) B-005.
- Depo/muhasebe yazılımı ve ürün fotoğraflarının yeri: BİLİNMİYOR — bkz. B-002.

## Avito platform notları

Kaynak: T-002 teslim metni (Main Agent kabul etti; metin repoda yok — bkz. B-012). Güven etiketleri: [INTEGRATIONS.md](INTEGRATIONS.md) başındaki tablo.

- "Товары" sohbetlerinde iletişim bilgisi (telefon, e-posta, sosyal ağ kullanıcı adı) göndermek ve istemek yasak (22 Mayıs 2024'ten beri; belgeyle doğrulanmış profesyonel profiller hariç); ihlal hesabın engellenmesine yol açabiliyor. → Giden mesajlar için bu bilgileri engelleyen bir çıktı filtresi gerekir. — ikincil kaynak
- Platform dışı ödeme veya anlaşma önermemek entegratörlerin tavsiyesi; resmî kural metni doğrulanamadı. → Çıktı filtresi bu önerileri de engellemeli. — ikincil kaynak
- Avito'nun yerleşik "Автоответы" (otomatik yanıt) özelliği satıcı yaklaşık 5 dakika çevrimdışı olduğunda çalışıyor; asistanla birlikte çalışırsa müşteriye çift yanıt gidebilir, kapatılmalı veya asistanla koordine edilmeli. — ikincil kaynak (otomatik yanıtların sistem mesajı olarak görünmesi: [INTEGRATIONS.md](INTEGRATIONS.md) §3.2)
- Anında gönderilen, hep aynı metinli, spam benzeri yanıtların yaptırıma yol açtığı iddia ediliyor. AI asistan kullanımını yasaklayan veya ifşa zorunluluğu getiren bir kural bulunamadı (doğrulanamadı). — ikincil kaynak
- API'den gelen tasarım kısıtları (metin uzunluk sınırı → uzun cevap bölünür; silme penceresi → hatalı gönderimi geri alma bu süreyle sınırlı; okuma sohbeti okundu yapmaz, `chatRead` ayrı çağrı): değerler ve etiketleri [INTEGRATIONS.md](INTEGRATIONS.md) §3.1'de.

## Ürün ve uyumluluk notları

(Henüz kaynaklı not yok.)

## Uygulama notları

(Henüz uygulama yok.)
