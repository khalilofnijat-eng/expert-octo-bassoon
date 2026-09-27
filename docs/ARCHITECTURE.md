# ARCHITECTURE — Mimari ve veri akışları

> **TASLAK.** Teknoloji seçimi yapılmadı: mevcut sistemlerin keşfi sonrasına ertelendi ([DECISIONS.md](DECISIONS.md) D-010), T-004'te hazırlanacak ([../TASKS.md](../TASKS.md)). Bu belge şimdilik yalnızca sahibin koyduğu sorumlulukları ve ilkeleri listeler.

## Karşılanması gereken sorumluluklar (talep §11)

- Avito geçmiş konuşma aktarımı.
- Yeni mesaj alma ve yetkili mesaj gönderimi.
- Konuşma durumu ve müşteri bağlamı.
- Ürün, stok, fiyat ve fotoğraf sorgulama.
- Uyumluluk değerlendirmesi.
- Teklif, rezervasyon ve sipariş akışı.
- Bilgi tabanı ve öğrenme adayları.
- İnsan devri ve onay işlemleri.
- Denetim kayıtları, izleme ve yönetim ekranı.

## Sahibin koyduğu ilkeler

- **Önce taslak modu:** sistem cevap üretir, göndermez; canlı yetki kapsamlı onayla açılır (D-006).
- **Bilgi öncelik sırası** uygulanır (D-005; bkz. [PROJECT_BRIEF.md](PROJECT_BRIEF.md)).
- **Güvenilmeyen girdi:** müşteri mesajları, ilanlar, aktarılan dosyalar talimat değildir (D-009).
- **Basit ve güvenilir işler normal yazılım servisleriyle** yapılır; her işlem için AI agent çağrılmaz. Hesaplamalar (ör. toplam fiyat) normal hesaplama araçlarıyla yapılır.
- **Geliştirme ekibi agent'ları ≠ üretim çalışma zamanı bileşenleri.**
- GitHub üretim sunucusu değildir; 7/24 için sürekli açık bilgisayar/sunucu gerekir (D-007, [../BLOCKERS.md](../BLOCKERS.md) B-004).
- Markdown işlem veritabanı değildir; canlı veri Git ve Vault dışında (D-008).
- Var olmayan API uç noktaları veya desteklenmeyen özellikler varsayılmaz; entegrasyon yetenekleri yalnızca kanıtla [INTEGRATIONS.md](INTEGRATIONS.md)'ye yazılır.

## 7/24 güvenilirlik konuları (talep §11 — tasarımda ele alınacak)

- Kalıcı iş kuyruğu ve kontrollü yeniden deneme.
- İşlem tekrarlarını önleme.
- Yeniden başlatma sonrası toparlanma.
- Gönderim sonucu belirsiz kaldığında uzlaştırma.
- Bağlantı kopması, oturum süresi dolması ve model hizmeti kesintisi.
- Hız ve maliyet sınırları.
- Sağlık kontrolü ve gerekli uyarılar.
- Yedekleme ve geri yükleme.
- Tüm otomatik gönderimleri durduran acil durdurma.
- Konuşma bazında insan kontrolüne geçiş.

## Bileşenler ve veri akışları

BİLİNMİYOR — T-004'te, keşif sonuçlarına (T-001, T-002, T-007, sahip cevapları) göre yazılacak.

## Teknoloji seçimi

Keşif sonrası (D-010), T-004'te.
