# T-011 — Görev kurallarının B-012'ye uyarlanması

- **Aşama:** 2 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Dokümantasyon agent'ı
- **Tarih:** 2026-09-27

## Amaç

Alt agent'ların rapor dosyası yazamaması ([BLOCKERS](../../BLOCKERS.md) B-012) nedeniyle görev kurallarını uyarlamak: teslim raporu Main Agent'a metin olarak, rapor şablonu yapısında verilir; sahip B-012 hakkında karar verene kadar diske yazılmaz; kabul edilen bulgular ilgili kayıtlara işlenir.

## Kapsam
- Dahil: [AGENTS.md](../../AGENTS.md) §3, [tasks/README.md](../README.md), şablonlar, T-001/T-002 brief'leri; [TASKS.md](../../TASKS.md) (T-010 bağımlılığına B-009, T-011 satırı); GitHub varsayılan dalının salt okunur GitHub aracıyla doğrulanıp [docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md) GitHub satırına tarihli yazılması; [docs/LESSONS_LEARNED.md](../../docs/LESSONS_LEARNED.md) B-012 kaydı; CHANGELOG.
- Hariç: `docs/ARCHITECTURE.md` (T-004'e ait); diğer kayıtlar.

## Bağımlılıklar
- T-009 (kabul edildi).

## Dosya sahipliği
- Yazabileceği dosyalar: `AGENTS.md`, `tasks/README.md`, `tasks/_TEMPLATE/brief.md`, `tasks/_TEMPLATE/report.md`, `tasks/T-001/brief.md`, `tasks/T-002/brief.md`, `tasks/T-011/brief.md`, `TASKS.md`, `CHANGELOG.md`, `docs/INTEGRATIONS.md` (yalnızca GitHub satırı), `docs/LESSONS_LEARNED.md` (yalnızca B-012 kaydı).
- Dokunmayacağı dosya: `docs/ARCHITECTURE.md` (değiştirilmez, stage edilmez).

## Beklenen çıktı
- Güncellenmiş dosyalar; `claude/youthful-goldberg-l427nm` dalına push edilmiş commit.
- Teslim raporu: Main Agent'a **metin olarak**, [rapor şablonu](../_TEMPLATE/report.md) yapısında (rapor dosyası yok — B-012).

## Kabul ölçütleri
- [ ] Rapor dosyası isteyen kural/brief kalmadı (T-003'ün kabul edilmiş raporu istisna).
- [ ] GitHub varsayılan dalı araç çıktısıyla doğrulanmış ve tarihli kayıtlı.
- [ ] Bağlantı denetimi: 0 kırık bağlantı.
- [ ] Yalnızca açık yollarla stage; `docs/ARCHITECTURE.md` stage edilmemiş.
