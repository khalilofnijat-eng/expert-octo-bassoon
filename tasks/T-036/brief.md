# T-036 — ARCHITECTURE rev.2 commit'i + kayıt eşitlemesi

- **Aşama:** 2 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Dokümantasyon agent'ı
- **Tarih:** 2026-09-27

## Amaç

Sahip onayıyla (2026-09-27: "Mimari belgesini GitHub'a göndermek için onay veriyorum."; B-013) kabul edilmiş mimari rev.2'yi commit etmek ve ortak kayıtları son kabul/red kararlarıyla eşitlemek.

## Kapsam
- Dahil: `docs/ARCHITECTURE.md` başlığı ve yalnızca belirtilen düzeltmeler (§6.10 uç nokta başına bucket; §10.1 M10, M11; §7.4 `[TYPE_n]`) — ayrı commit. Ardından ikinci commit: TASKS, BLOCKERS (B-001, B-005, B-013), DECISIONS (D-039–D-041), INTEGRATIONS, T-010 brief'i, `tests/README.md`, `.env.example` (yalnızca `APP_ENV` satırı), STATE, HANDOFF, oturum kaydı, CHANGELOG, TEST_REPORT ve brief'ler.
- Hariç: kod, `app/README.md` (gereken değişiklikler teslim metninde listelenir).

## Bağımlılıklar
- B-013 (sahip onayı).

## Dosya sahipliği
- Yazabileceği dosyalar: kapsamdaki dosyalar.
- Dokunmayacağı dosyalar: kod, `app/README.md`, `docs/OWNER_REQUEST_*`.

## Beklenen çıktı
- İki push edilmiş commit; hash'ler ve `git status` teslim metninde.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
- [ ] Bağlantı denetimi 0 kırık bağlantı gösteriyor.
- [ ] Okuma simülasyonu (AGENTS §1 sırası) doğru sonraki eylemleri veriyor.
- [ ] İki commit push edildi.
