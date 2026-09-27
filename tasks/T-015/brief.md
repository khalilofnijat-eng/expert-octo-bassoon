# T-015 — Çekirdek tablolar + kilitler + CAS

- **Aşama:** 6 ve 9 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27

## Amaç

Konuşma, mesaj, kuyruk, taslak ve outbox'ın dayandığı çekirdek tabloları ve eşzamanlılık güvencelerini (advisory lock, fencing, CAS) kurmak ve testlerle kanıtlamak.

## Kapsam
- Dahil: `conversation`, `message`, `job`, `draft`, `outbound_message`, `system_setting`, `audit_event` tablolarının migration'ı; worker singleton kilidi ve konuşma kilidi (iki anahtarlı ad alanı); yeniden kuyruğa alma birleştirme kuralı; koşullu draft INSERT; CAS geçişleri; audit rolünün UPDATE/DELETE yapamaması. Tasarım: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §5, §6.1, §6.2; kararlar D-023, D-024.
- Singleton fencing yöntemi (pg_locks koşulu ya da singleton bağlantısından yazma) bu görevin testleriyle seçilir ve teslim metninde gerekçelendirilir (D-024).
- Hariç: Avito çağrıları, outbox gönderimi (T-025), diğer tablolar.

## Bağımlılıklar
- T-014.

## Dosya sahipliği
- Yazabileceği dosyalar: `app/` ve `tests/` altındaki bu görevin dosyaları, migration dosyaları; gerekirse `pyproject.toml`/`uv.lock`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler gerçek PostgreSQL üzerinde çalışır; sonuçlar "sentetik" olarak raporlanır.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
Tam metin: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §14, T-015 satırı. Özet:
- [ ] Migration temiz kuruluyor.
- [ ] Y1 (ölü `running` job'ın birleştirme kuralı; crash-restart döngüsü yok), Y2 (re-entrancy tuzağı; kilit bağlantısı havuzdan ayrı ve havuza dönmüyor), Y5 (singleton oturumu ölünce süreç çıkıyor, fencing'li CAS 0 satır), Y6 (kilit alınamayan job `done` olmuyor; (1, x) ve (2, x) çakışmıyor) testleri.
- [ ] `queued` tekilliği; çalışan iş sırasında gelen mesaj kaybolmuyor; koşullu draft INSERT stale'i reddediyor; CAS yarışı; audit rolü UPDATE/DELETE yapamıyor.
- [ ] **Bağımsız inceleme zorunlu** (geliştiren dışında bir agent).
