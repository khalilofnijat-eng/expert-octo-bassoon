# T-003 — Kalıcı kayıt düzeni iskeleti

- **Aşama:** 2 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Dokümantasyon agent'ı
- **Tarih:** 2026-09-27

## Amaç

Hiçbir kritik bilginin yalnızca sohbette veya agent hafızasında kalmaması için projenin kalıcı kayıt düzenini kurmak (talep §9–10) ve bugün bilinen gerçek içerikle doldurmak.

## Kapsam
- Dahil: kök kayıtlar (README, AGENTS, CLAUDE, STATE, HANDOFF, TASKS, BLOCKERS, CHANGELOG, .gitignore); `docs/` belgeleri (OWNER_REQUEST kelimesi kelimesine, PROJECT_BRIEF, ARCHITECTURE taslağı, PLAN, DECISIONS D-001…D-010, NOTES, LESSONS_LEARNED, INTEGRATIONS, TEST_REPORT, RUNBOOK); `sessions/`; `tasks/` (README, şablonlar, T-001…T-003 brief'leri, T-003 raporu); `knowledge/`, `operations/`, `app/`, `tests/`, `scripts/`, `data/` README'leri; commit ve push.
- Hariç: uygulama kodu; teknoloji seçimi; işletme hakkında varsayım.

## Bağımlılıklar
- Yok.

## Dosya sahipliği
- Yazabileceği dosyalar: yukarıdaki düzenin tamamı.
- Dokunmayacağı dosyalar: `tasks/T-001/report.md`, `tasks/T-002/report.md` (değiştirilmez, stage edilmez).

## Beklenen çıktı

Düzen dosyaları + `tasks/T-003/report.md`; `claude/youthful-goldberg-l427nm` dalına push edilmiş commit.

## Kabul ölçütleri
- [ ] Tüm dosyalar mevcut; göreli bağlantılar çözülüyor (bağlantı denetleyicisi çıktısıyla).
- [ ] OWNER_REQUEST metni birebir (diff ile doğrulanmış).
- [ ] Uydurulmuş işletme bilgisi yok; bilinmeyenler BLOCKERS kimliklerine bağlı; gereksiz tekrar yok; gizli değer yok.
- [ ] T-001/T-002 rapor dosyaları stage edilmemiş/değiştirilmemiş.
- [ ] Commit push edilmiş; hash ve son `git status` raporlanmış.
