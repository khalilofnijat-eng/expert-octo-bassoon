# NOTES — İşletme ve uygulama notları

Yalnızca kaynağı belirtilmiş notlar yazılır. Kararlar [DECISIONS.md](DECISIONS.md)'de, engeller [../BLOCKERS.md](../BLOCKERS.md)'de, entegrasyon yetenekleri [INTEGRATIONS.md](INTEGRATIONS.md)'de tutulur.

## İşletme notları

- İşletme Avito'da otomotiv parçası satıyor. — kaynak: [OWNER_REQUEST_2026-09-27.md](OWNER_REQUEST_2026-09-27.md) §2
- Sahiple iletişim Türkçe; müşterilerle müşterinin dilinde, Rusça konuşmalar özellikle desteklenecek. — kaynak: OWNER_REQUEST §2
- Örnek satış senaryosu: Mercedes W213 ön tampon + uyumlu ızgara seçimi. — kaynak: OWNER_REQUEST §6
- Fiyat, indirim, teslimat, ödeme, rezervasyon, iade/garanti ve insana devir kuralları: BİLİNMİYOR — bkz. [../BLOCKERS.md](../BLOCKERS.md) B-005.
- Depo/muhasebe yazılımı ve ürün fotoğraflarının yeri: BİLİNMİYOR — bkz. B-002.

## Avito platform notları

Kaynak: T-002 raporu (Main Agent kabul etti; repoda dosya olarak yok — B-012). Aksi belirtilmedikçe **ikincil kaynak**.

- "Товары" sohbetlerinde iletişim bilgisi (telefon, e-posta, sosyal ağ kullanıcı adı) göndermek ve istemek yasak (2024'ten beri; belgeyle doğrulanmış profesyonel profiller hariç); ihlal hesabın engellenmesine yol açabiliyor. → Giden mesajlar için bu bilgileri engelleyen bir çıktı filtresi gerekir. — ikincil kaynak
- Avito'nun yerleşik "Автоответы" (otomatik yanıt) özelliği asistanla birlikte çalışırsa müşteriye çift yanıt gidebilir; kapatılmalı veya asistanla koordine edilmeli. — ikincil kaynak (otomatik yanıt mesajlarının sistem mesajı olarak göründüğü: resmî spec kopyası)
- Metin mesajı en fazla 1000 karakter; uzun cevaplar bölünmeli. — resmî spec kopyası
- API ile mesaj okumak sohbeti okundu olarak işaretlemez; okundu yapmak ayrı bir çağrıdır (`chatRead`). — resmî spec kopyası
- Gönderilen mesaj yalnızca 1 saat içinde silinebilir; hatalı gönderimi geri alma bu süreyle sınırlı. — resmî spec kopyası
- Resmî spec'teki metin gönderme gövde şemasında hata var (gereksiz yere `required: ["url"]`); istemci yazılırken şemaya körü körüne güvenilmemeli. — resmî spec kopyası

## Ürün ve uyumluluk notları

(Henüz kaynaklı not yok.)

## Uygulama notları

(Henüz uygulama yok.)
