# T-017 — Avito gateway (okuma) + spec tabanlı mock

- **Aşama:** 3 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

Avito Messenger/Items okuma uçları için kendi ince istemcimizi (D-013) ve ağsız, spec tabanlı bir mock'u yazmak; T-010 ölçüm betiği ve T-020/T-021 bu istemciyi kullanır.

## Kapsam
- Dahil: token (`client_credentials`, `expires_in`), `accounts/self`, chats v2, chat v2, messages v3, `getVoiceFiles`, items; salt okunur izin listesi ve transport guard; uç nokta başına öncelikli rate limiter (`live` > `bulk`, [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §6.10); okuma hata sınıfları; sonlanması garanti sayfalama; mock (sentetik veri, kayan offset, hata enjeksiyonu). Uçlar: [docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md) §3.1.
- Hariç: gönderim ve Avito'da yazan her çağrı ([AGENTS.md](../../AGENTS.md) §6), gerçek Avito çağrısı (B-007, B-009, B-011).

## Bağımlılıklar
- T-014.

## Dosya sahipliği
- Yazabileceği dosyalar: `app/avito_gateway/`, `scripts/dev/avito_mock/`, `tests/avito/`, `tests/fixtures/avito/`; gerekirse `pyproject.toml`/`uv.lock`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler yalnızca mock ve sentetik veriyle.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
Tam metin: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §14, T-017 satırı. Özet:
- [ ] Yazan hiçbir uca ulaşılamadığını gösteren test (izin listesi + transport guard).
- [ ] Token `expires_in` ile yönetiliyor; öncelikli rate limiter (`live` > `bulk`).
- [ ] Okuma hata sınıfları; transport retry yok.
- [ ] Mock kararlı ve kayan offset'le sayfalıyor; sayfalama her zaman sonlanıyor.
