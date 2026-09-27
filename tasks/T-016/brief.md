# T-016 — Mimari kabulü sonrası kayıt eşitlemesi ve T-010 kapsamı

- **Aşama:** 3 ([PLAN](../../docs/PLAN.md)); kayıt eşitlemesi aşama 2'nin kapanışı
- **Sahip (agent rolü):** Dokümantasyon agent'ı
- **Tarih:** 2026-09-27

## Amaç

Main Agent'ın 2026-09-27 kararlarını (T-004 rev.2 kabulü; T-012, T-012b, T-013, T-014 kabulü; T-013b'nin yapılamaması) kayıtlara işlemek ve T-010 ölçüm betiğinin kapsamını ([docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §10.1, §14) brief olarak yazmak.

## Kapsam
- Dahil: [tasks/T-010/brief.md](../T-010/brief.md) (M1–M9, okundu yan etkisinin canlı doğrulaması, ölçüm yöntemi, çıktı biçimi, kabul ölçütleri, güvenlik kontrol listesi); [docs/DECISIONS.md](../../docs/DECISIONS.md) D-015–D-038; [TASKS.md](../../TASKS.md) (T-015…T-031, B-012 listesi); [BLOCKERS.md](../../BLOCKERS.md) (B-013, B-014, sahibe sorulan ek sorular); T-012, T-013, T-014, T-015, T-016, T-019 brief'leri; `.gitignore`; [knowledge/README.md](../../knowledge/README.md); STATE, HANDOFF, oturum kaydı, CHANGELOG, PLAN.
- Hariç: `docs/ARCHITECTURE.md` (değiştirilmez, stage edilmez; commit'i B-013 bekliyor), `docs/OWNER_REQUEST_*`, `app/`, `tests/*.py`, `pyproject.toml`, `uv.lock`.

## Bağımlılıklar
- T-004 onayı (Main Agent, 2026-09-27).

## Dosya sahipliği
- Yazabileceği dosyalar: kapsamdaki Markdown kayıtları, `tasks/*/brief.md`, `.gitignore`.
- Aynı çalışma ağacında T-015 ve T-019 da commit eder: yalnızca açık yollarla stage ve `git commit -- <yollar>`.

## Beklenen çıktı
- Push edilmiş commit; teslim raporu Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] T-010 brief'i M1–M9 kalemlerini, ölçüm yöntemini ve çıktı biçimini içeriyor (ARCHITECTURE §14).
- [ ] Bağlantı denetimi: 0 kırık bağlantı.
- [ ] AGENTS → STATE → HANDOFF → TASKS → BLOCKERS okuması doğru sıradaki eylemleri veriyor.
- [ ] `docs/ARCHITECTURE.md` değişmemiş ve stage edilmemiş.
