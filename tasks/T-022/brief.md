# T-022 — Inventory port + sentetik adaptör + catalog/fitment

- **Aşama:** 5 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

Depo sistemi bilinmezken (B-002) salt okunur bir inventory portu, açıkça etiketli sentetik bir adaptör ve deterministik bir uyumluluk (fitment) motoru yazmak.

## Kapsam
- Dahil: port arayüzü (arama, ürün, stok, fiyat, fotoğraf, sağlık; her olgunun kaynağı ve zamanı); sentetik W213 veri seti (`SYN-`; üretimde başlamaz, `APP_ENV` boş/bilinmiyorsa üretim sayılır); `verified` yalnızca izinli kanıtla; sanal set semantiği (D-033); stok bağlantısı yokken `unknown`; ilgili tabloların migration'ı.
- Hariç: gerçek depo adaptörü (B-002), depoya yazma (D-019).
- Ek karar (T-022b): doğrulanmış aralık dışındaki araç `incompatible` değil `needs_verification` olur; `incompatible` yalnızca kanıtlı açık uyumsuzluk kaydıyla ([TASKS.md](../../TASKS.md) T-022b).

## Bağımlılıklar
- T-014.

## Dosya sahipliği
- Yazabileceği dosyalar: `app/inventory/`, `app/catalog/`, `app/db/models.py` (yalnızca ekleme), yeni migration dosyası, `tests/catalog/`, `tests/inventory/`, `tests/fixtures/synthetic_catalog/`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler sentetik veriyle (DB kısımları gerçek PostgreSQL'de).
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
Tam metin: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §14, T-022 satırı. Özet:
- [ ] Port arayüzü; etiketli sentetik veri seti üretimde başlamıyor.
- [ ] `verified` yalnızca izinli kanıtla; sanal set; stok bağlantısı yokken `unknown`.
