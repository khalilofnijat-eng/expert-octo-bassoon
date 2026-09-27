# TEST_REPORT — Çalıştırılan testler ve sonuçları

Deneme (sentetik) veriyle yapılan testler ile gerçek sistemde yapılan testler **kesinlikle ayrı** raporlanır (talep §14). Sentetik veriyle başarılı bir test, gerçek entegrasyonun çalıştığı anlamına gelmez.

Durum: yalnızca sentetik testler var (birim testleri ve geçici gerçek PostgreSQL 16 üzerinde DB testleri; Avito yalnızca mock). **Gerçek sistemde (Avito, depo, LLM) hiçbir test yapılmadı.**

CI (GitHub Actions, [../.github/workflows/ci.yml](../.github/workflows/ci.yml)): ruff, ruff format, mypy, (T-015'ten beri) temiz veritabanında Alembic upgrade ve pytest. Test sayıları CI günlüğündeki pytest özetidir. "xfailed" = `xfail(strict=True)` ile işaretli bilinen sınırlamalar.

## Deneme (sentetik) veriyle testler

| Tarih | Test | Sürüm/commit | Sonuç | Kanıt |
|---|---|---|---|---|
| 2026-09-27 | T-014: PII maskeleyici, ayarlar, `/healthz` birim testleri; ruff, ruff format, mypy (CI) | `11694f5` | 74 test geçti, 7 bilinen sınırlama `xfail(strict=True)`; CI çalıştırması #1 başarılı | GitHub Actions run id 36340790249; commit mesajı `11694f5`; kapsam: [../tests/README.md](../tests/README.md) |
| 2026-09-27 | T-019: output filter (+ önceki testler) | `ecb73e0` | 203 geçti, 16 xfailed; CI #3 başarılı | run id 36342169787 |
| 2026-09-27 | T-015: çekirdek tablolar, kuyruk, kilitler, CAS (gerçek PostgreSQL 16, CI servis konteyneri) | `747775e` | 237 geçti, 16 xfailed; CI #4 başarılı | run id 36342287028 |
| 2026-09-27 | T-022: inventory portu, sentetik adaptör, catalog/fitment (sentetik W213 veri seti) | `2e0e2d3` | 319 geçti, 16 xfailed; CI #5 başarılı | run id 36343832293 |
| 2026-09-27 | T-017: Avito okuma istemcisi, spec tabanlı mock (ağ yok) | `57e2029` | 470 geçti, 16 xfailed; CI #6 başarılı | run id 36343844016 |
| 2026-09-27 | T-022b: fitment kuralı | `fb6c0ea` | 473 geçti, 16 xfailed; CI #7 başarılı | run id 36344099809 |
| 2026-09-27 | T-018: metin gönderim istemcisi (mock) — kabul kararı kayıtta yok | `c86b942` | 540 geçti, 16 xfailed; CI #8 başarılı | run id 36344368388 |
| 2026-09-27 | T-034: masker + filter düzeltmeleri, T-032 regresyon testleri — kabul kararı kayıtta yok | `9bb67b7` | 1412 geçti, 31 xfailed; CI #9 başarılı | run id 36344523446 |
| 2026-09-27 | T-018b: gönderimde `ProxyError` → `unknown` — kabul kararı kayıtta yok | `3a5f198` | CI #10 başarılı (test sayısı okunmadı) | run id 36344687965 |
| 2026-09-27 | T-035: T-015 düzeltmeleri (SIGKILL çökme testleri dahil) | `15da795` | 1446 geçti, 31 xfailed; CI #11 başarılı | run id 36344758297 |
| 2026-09-27 | T-018c: gönderim istemcisinde ortak `measure_part` | `afd6ad5` | 1452 geçti, 31 xfailed; CI #13 başarılı | run id 36344867417 |

## Gerçek sistemde testler

| Tarih | Test | Sürüm/commit | Sonuç | Kanıt |
|---|---|---|---|---|
| — | Henüz test yok. | — | — | — |
