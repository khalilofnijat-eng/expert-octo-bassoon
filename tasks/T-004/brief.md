# T-004 — Mimari taslağı (teknoloji seçimi keşif sonrası)

- **Aşama:** 2 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Mimari agent'ı
- **Tarih:** 2026-09-27

## Amaç

Keşif bulgularına dayanarak sistemin mimarisini ve veri akışlarını taslak olarak yazmak, teknoloji önerisi hazırlamak (D-010: seçim keşif sonrası).

## Kapsam
- Dahil: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) yeniden yazımı: bileşenler, veri akışları, sahibin ilkeleri ve 7/24 güvenilirlik konularının nasıl karşılanacağı; teknoloji önerisi ve gerekçesi.
- Girdiler: [docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md), [docs/NOTES.md](../../docs/NOTES.md), [docs/DECISIONS.md](../../docs/DECISIONS.md) (özellikle D-006–D-013), [BLOCKERS.md](../../BLOCKERS.md). T-001/T-002 rapor metinleri Main Agent'tadır (B-012).
- Hariç: uygulama kodu; kurulum; dış sisteme çağrı.

## Bağımlılıklar
- T-001, T-002 (kabul edildi).

## Dosya sahipliği
- Yazabileceği dosya: yalnızca `docs/ARCHITECTURE.md`.
- Karar önerileri (ör. teknoloji seçimi) Main Agent'a iletilir; kabul edilenleri Dokümantasyon agent'ı [docs/DECISIONS.md](../../docs/DECISIONS.md)'ye kaydeder. T-004 ortak kayıtlara yazmaz.

## Beklenen çıktı

Güncellenmiş `docs/ARCHITECTURE.md` ve Main Agent'a **metin olarak** teslim raporu (yapılan iş, değişen dosyalar, doğrulama kanıtı, kalan sorunlar, sorular, sonraki adım). Rapor dosyası beklenmez (B-012).

## Kabul ölçütleri
- [ ] Var olmayan API uç noktası veya doğrulanmamış yetenek varsayılmaz; yetenekler INTEGRATIONS'taki güven etiketleriyle kullanılır.
- [ ] Bilinmeyenler BLOCKERS kimliklerine bağlanır.
- [ ] Basit ve güvenilir işler normal yazılım servisleriyle yapılır; geliştirme agent'ları ile üretim bileşenleri ayrıdır.
- [ ] Teknoloji önerileri gerekçeli ve "öneri" olarak işaretli; karar olarak yazılmaz.
