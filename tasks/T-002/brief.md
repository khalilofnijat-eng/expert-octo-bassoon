# T-002 — Avito resmî entegrasyon araştırması

- **Aşama:** 1 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Araştırma agent'ı
- **Tarih:** 2026-09-27

## Amaç

Resmî kaynaklardan Avito entegrasyon olanaklarını ve erişim koşullarını belirlemek.

## Kapsam
- Dahil: Avito API erişim koşulları; Messenger API (sohbet listeleme, geçmiş, gönderim, fotoğraf, okundu işaretleme, webhook); Items API; hız sınırları; bot / otomasyon / tarayıcı otomasyonu kuralları; 152-FZ uyum notu.
- Hariç: kimlik doğrulamalı API çağrısı.

## Bağımlılıklar
- Yok. (Sonuçları [B-007](../../BLOCKERS.md) ve T-006'yı etkiler.)

## Dosya sahipliği
- Yazabileceği dosya: yok (salt okunur görev).

## Beklenen çıktı

Main Agent'a **metin olarak** teslim raporu ([şablon](../_TEMPLATE/report.md) yapısında), her bulguya resmî kaynak bağlantısıyla. Rapor dosyası beklenmez ([BLOCKERS](../../BLOCKERS.md) B-012).

> Not (T-011, 2026-09-27): Bu brief ilk hâlinde `tasks/T-002/report.md` dosyasını istiyordu; alt agent'ların rapor dosyası yazamadığı anlaşıldıktan sonra B-012 kuralına uyarlandı.

## Kabul ölçütleri
- [ ] Resmî kaynağı olmayan yetenek "destekleniyor" diye yazılmaz.
- [ ] Bilinmeyenler açıkça işaretlenir.
