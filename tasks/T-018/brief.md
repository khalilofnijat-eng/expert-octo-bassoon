# T-018 — Gönderim istemcisi (yalnızca metin)

- **Aşama:** 7 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27 (brief kaydı: T-036)

## Amaç

Tek bir metin mesajını Avito'ya gönderen, otomatik yeniden deneme yapmayan ve sonucu `delivered` / `not_delivered` / `unknown` olarak sınıflandıran istemciyi yazmak (D-015). Outbox (T-025) bu istemciyi kullanır.

## Kapsam
- Dahil: yalnızca metin gönderim ucu ([docs/INTEGRATIONS.md](../../docs/INTEGRATIONS.md) §3.1); okuma izin listesinden ayrı bir yazma izin listesi; hata sınıflandırması; transport retry / retry middleware / redirect yok; her HTTP denemesi ayrı attempt kaydı; mock'ta hata enjeksiyonu; parça uzunluğu kontrolü.
- Hariç: görsel gönderimi (D-032), outbox ve DB (T-025), gerçek Avito çağrısı.

## Bağımlılıklar
- T-017.

## Dosya sahipliği
- Yazabileceği dosyalar: `app/avito_gateway/` (gönderim modülü), `scripts/dev/avito_mock/`, `tests/avito/`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler yalnızca mock ve sentetik veriyle.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
Tam metin: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §14, T-018 satırı. Özet:
- [ ] Metin gönderimi; hata sınıflandırması; otomatik yeniden deneme olmadığını kanıtlayan test.
- [ ] Transport retry, retry middleware ve redirect yok; her HTTP denemesi ayrı attempt.
- [ ] Okuma istemcisi hâlâ hiçbir yazan uca ulaşamıyor.
- [ ] **Bağımsız inceleme zorunlu**, T-025 ile birlikte (geliştiren dışında bir agent).
