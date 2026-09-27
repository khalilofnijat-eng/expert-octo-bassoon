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
- Yazabileceği dosya: yalnızca `tasks/T-002/report.md`.

## Beklenen çıktı

`tasks/T-002/report.md` ([şablon](../_TEMPLATE/report.md) biçiminde), her bulguya resmî kaynak bağlantısıyla.

## Kabul ölçütleri
- [ ] Resmî kaynağı olmayan yetenek "destekleniyor" diye yazılmaz.
- [ ] Bilinmeyenler açıkça işaretlenir.
