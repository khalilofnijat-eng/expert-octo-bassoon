# TEST_REPORT — Çalıştırılan testler ve sonuçları

Deneme (sentetik) veriyle yapılan testler ile gerçek sistemde yapılan testler **kesinlikle ayrı** raporlanır (talep §14). Sentetik veriyle başarılı bir test, gerçek entegrasyonun çalıştığı anlamına gelmez.

Durum: yalnızca sentetik birim testleri var (T-014). Gerçek sistemde test yapılmadı.

## Deneme (sentetik) veriyle testler

| Tarih | Test | Sürüm/commit | Sonuç | Kanıt |
|---|---|---|---|---|
| 2026-09-27 | T-014: PII maskeleyici, ayarlar, `/healthz` birim testleri; ruff, ruff format, mypy (CI) | `11694f5` | 74 test geçti, 7 bilinen sınırlama `xfail(strict=True)`; CI çalıştırması #1 başarılı | GitHub Actions run id 36340790249; commit mesajı `11694f5`; kapsam: [../tests/README.md](../tests/README.md) |

## Gerçek sistemde testler

| Tarih | Test | Sürüm/commit | Sonuç | Kanıt |
|---|---|---|---|---|
| — | Henüz test yok. | — | — | — |
