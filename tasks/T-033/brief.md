# T-033 — T-015 bağımsız incelemesi

- **Aşama:** 6 ve 9 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** İnceleme agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

Çekirdek tabloları, kuyruğu, advisory lock'ları ve CAS'ı (T-015, commit `747775e`) geliştiren dışında bir agent olarak bağımsız ve salt okunur incelemek (T-015 için zorunlu inceleme).

## Kapsam
- Dahil: `app/db/`, `app/queue/`, `migrations/`, `tests/db/`; [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §5, §6.1, §6.2 ve D-023, D-024'e uygunluk; T-015 kabul ölçütleri.
- Hariç: dosya değiştirmek (düzeltmeler ayrı görev: T-035).

## Bağımlılıklar
- T-015.

## Dosya sahipliği
- Yazabileceği dosyalar: yok (salt okunur).

## Beklenen çıktı
- Her bulgu: dosya/satır kanıtı, önerilen düzeltme, önem derecesi.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] Bulgular kanıtlı; düzeltme önerisi ve önem derecesi var.
- [ ] Hiçbir dosya değiştirilmedi.
