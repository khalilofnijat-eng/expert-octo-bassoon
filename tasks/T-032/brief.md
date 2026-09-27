# T-032 — Masker ve output filter bağımsız güvenlik incelemesi

- **Aşama:** 6 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** İnceleme agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

PII maskeleyicinin (T-014) ve output filter'ın (T-019) atlatılıp atlatılamadığını, geliştiren dışında bir agent olarak bağımsız ve salt okunur incelemek ([AGENTS.md](../../AGENTS.md) §2).

## Kapsam
- Dahil: `app/safety/` ve testleri; [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §7.2 ve §7.4 kurallarına uygunluk; kaçan ve fazla engellenen örnekler.
- Hariç: dosya değiştirmek (düzeltmeler ayrı görev: T-034).

## Bağımlılıklar
- T-014, T-019.

## Dosya sahipliği
- Yazabileceği dosyalar: yok (salt okunur).

## Beklenen çıktı
- Her bulgu: dosya/satır kanıtı, yeniden üretim, önerilen düzeltme, önem derecesi.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] Bulgular kanıtlı ve yeniden üretilebilir; düzeltme önerisi ve önem derecesi var.
- [ ] Hiçbir dosya değiştirilmedi.
