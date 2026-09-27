# T-035 — T-015 düzeltmeleri (T-033 bulguları)

- **Aşama:** 6 ve 9 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

T-033 incelemesinde kabul edilen bulguları çekirdek DB, kuyruk ve kilit katmanında düzeltmek.

## Kapsam
- Dahil: `app/db/`, `app/queue/`, `app/config.py`, migration 0001 ve `tests/db/` düzeltmeleri; `app/README.md`'nin ilgili bölümleri.
- Hariç: diğer görevlerin modülleri (`app/safety/`, `app/avito_gateway/`).

## Bağımlılıklar
- T-033.

## Dosya sahipliği
- Yazabileceği dosyalar: yukarıdaki kapsam.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler gerçek PostgreSQL üzerinde, sentetik veriyle.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] T-033'ün kabul edilen her bulgusu düzeltildi ve testle gösterildi; CI başarılı.
