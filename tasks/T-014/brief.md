# T-014 — Proje iskeleti + PII masker

- **Aşama:** 6 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27

> Bu brief, görev tamamlandıktan sonra T-016 ile kayda geçirildi. Kaynak: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §14 (T-014 satırı) ve §7.4. Sonuç: commit `11694f5`, CI çalıştırması #1 başarılı ([docs/TEST_REPORT.md](../../docs/TEST_REPORT.md)).

## Amaç

Uygulamanın Python proje iskeletini kurmak ve LLM'e giden metinlerdeki kişisel verileri maskeleyen PII maskeleyiciyi yazmak.

## Kapsam
- Dahil: uv projesi (Python 3.11), ruff, mypy, pytest, FastAPI iskeleti, ayarlar, `/healthz`; `app/` paket düzeni; PII maskeleyici (`[PHONE_1]` biçiminde tiplenmiş yer tutucular; ARCHITECTURE §7.4); yalnızca sentetik test verisi; CI.
- Hariç: veritabanı tabloları (T-015), Avito çağrısı, gerçek veri.

## Bağımlılıklar
- — (ARCHITECTURE §14).

## Dosya sahipliği
- Yazabileceği dosyalar: `app/`, `tests/`, `pyproject.toml`, `uv.lock`, CI yapılandırması, `.env.example`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.

## Beklenen çıktı
- Push edilmiş commit; teslim raporu Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] uv, ruff, pytest, FastAPI, SQLAlchemy/Alembic, PostgreSQL 16 iskeleti (ARCHITECTURE §14 metni). Gözlem (T-016): `11694f5`'teki `pyproject.toml` bağımlılıklarında SQLAlchemy/Alembic yok; veritabanı katmanı T-015 ile geliyor.
- [ ] Maskeleyici testleri (`[PHONE_1]` biçimi); bilinen sınırlamalar açıkça işaretli.
- [ ] Test verisi yalnızca sentetik; gizli değer commit edilmemiş.

Main Agent'ın teslimdeki sorular üzerine kararları: [docs/DECISIONS.md](../../docs/DECISIONS.md) D-036–D-038.
