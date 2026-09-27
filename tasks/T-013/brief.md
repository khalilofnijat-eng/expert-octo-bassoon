# T-013 — T-005 bulgularının düzeltilmesi

- **Aşama:** 2 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Dokümantasyon agent'ı
- **Tarih:** 2026-09-27

> Bu brief, görev tamamlandıktan sonra T-016 ile kayda geçirildi. Yapılan değişikliklerin listesi: [CHANGELOG](../../CHANGELOG.md) → T-013 kaydı (commit `8a51f3c`).

## Amaç

Kayıt düzeninin bağımsız incelemesinde (T-005) Main Agent'ın kabul ettiği bulguları düzeltmek.

## Kapsam
- Dahil: ortak Markdown kayıtları (tek kaynak ilkesi, tekrarların bağlantıyla değiştirilmesi), `.gitignore` genişletmesi, [AGENTS.md](../../AGENTS.md) eklemeleri, geliştirme dalı kararı D-014, T-012 ve T-013 satırları.
- Hariç: `docs/ARCHITECTURE.md` (T-004'e ait), `docs/OWNER_REQUEST_*` (değiştirilmez).

## Bağımlılıklar
- T-005.

## Dosya sahipliği
- Yazabileceği dosyalar: Dokümantasyon agent'ının Markdown kayıtları ve `.gitignore`.
- Dokunmayacağı dosyalar: `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.

## Beklenen çıktı
- `claude/youthful-goldberg-l427nm` dalına push edilmiş commit.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] Kabul edilen T-005 bulgularının her biri düzeltilmiş.
- [ ] Bağlantı denetimi: 0 kırık bağlantı.
- [ ] Yalnızca açık yollarla stage; `docs/ARCHITECTURE.md` stage edilmemiş.
