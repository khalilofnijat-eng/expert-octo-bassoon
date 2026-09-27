# T-034 — Masker + filter düzeltmeleri (T-032 bulguları)

- **Aşama:** 6 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

T-032 incelemesinde kabul edilen bulguları maskeleyicide ve output filter'da düzeltmek.

## Kapsam
- Dahil: `app/safety/` düzeltmeleri; T-032'nin her yeniden üretiminin regresyon testi olması; parça uzunluğu ölçüsü `measure_part` ([docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §10.1 M11).
- Hariç: yeni filtre kuralı için işletme kararı gerektiren değişiklikler (ör. nakit ödeme kuralının gevşetilmesi — D-039'daki takip görevi).

## Bağımlılıklar
- T-032.

## Dosya sahipliği
- Yazabileceği dosyalar: `app/safety/`, `tests/test_masker.py`, `tests/test_filter*.py`, `tests/fixtures/filter/`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler yalnızca sentetik veriyle.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] T-032'nin kabul edilen her bulgusu düzeltildi ya da bilinen sınırlama olarak `xfail(strict=True)` ile işaretlendi.
- [ ] Her yeniden üretim regresyon testi olarak var; CI başarılı.
