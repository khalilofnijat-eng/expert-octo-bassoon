# HANDOFF — Yeni oturum için devam özeti

**Son güncelleme:** 2026-09-27 (T-016)

Okuma sırası ve kurallar: [AGENTS.md](AGENTS.md) §1. Mevcut durum: [STATE.md](STATE.md). Görev durumları ve bağımlılıklar yalnızca [TASKS.md](TASKS.md)'de; engeller ve sahip cevapları yalnızca [BLOCKERS.md](BLOCKERS.md)'de.

## Nerede kaldık

Mimari rev.2 olarak kabul edildi (T-012 incelemesi, T-012b doğrulaması ve düzeltmelerden sonra); kararları [docs/DECISIONS.md](docs/DECISIONS.md) D-015–D-038'de. Ancak `docs/ARCHITECTURE.md` rev.2'nin commit'i izin sistemince reddedildi (T-013b) ve sahip izni bekleniyor (B-013): rev.2 yalnızca geçici konteynerin çalışma ağacında. Proje iskeleti ve PII maskeleyici tamamlandı (T-014). Uygulama dalgası (T-015…T-031) TASKS'ta; T-015 ve T-019 sürüyor. T-010 ölçüm betiğinin kapsamı yazıldı ([tasks/T-010/brief.md](tasks/T-010/brief.md)). Dış sistem bağlantısı yok; sahipten hiçbir engel için cevap gelmedi.

## Sıradaki eylemler

1. **Sahip cevapları:** özellikle B-013 (izin gelince `docs/ARCHITECTURE.md` rev.2 commit edilir ve başlığı TASLAK'tan kabul edildiye çevrilir), B-012, B-008; ayrıca 2026-09-27'de sorulan ek sorular (B-002, B-004, B-005, B-006, B-014). Cevap geldikçe BLOCKERS'ı ve bağlı görevleri güncellettir.
2. **Sürmekte olanlar:** T-015 ve T-019 (Geliştirici agent'ı) — gerçekten çalışıp çalışmadıklarını doğrula; teslimde zorunlu bağımsız incelemeleri başlat (T-015; T-019 incelemesi T-028 ile birlikte — [TASKS.md](TASKS.md)). T-016 teslimini değerlendir.
3. **Sonra:** T-017 (Avito gateway okuma + mock) ve T-018 (gönderim istemcisi). T-010, T-017 bittikten ve B-007, B-009, B-011 çözüldükten sonra sahibin makinesinde çalışır.
4. Diğer engelsiz görevler (mock/sentetik) bağımlılık sırasıyla: [TASKS.md](TASKS.md) → "Uygulama dalgası".

## Uyarılar

- Önceki agent'ların veya arka plan süreçlerinin hâlâ çalıştığını varsayma; sürmekte görünen görevlerin gerçek durumunu kontrol et.
- Konteyner geçicidir: push edilmemiş iş kaybolur. **`docs/ARCHITECTURE.md` rev.2 push edilmedi (B-013)**; D-015–D-038 ve TASKS'taki özetler kalıcıdır, ama §-numaralı ayrıntılar rev.2'dedir.
- Aynı çalışma ağacında birden fazla agent commit ediyor: yalnızca açık yollarla stage ve `git commit -- <yollar>`.
- Alt agent'lar rapor dosyası yazamaz; brief'lerde rapor dosyası isteme, teslimi metin olarak al (bkz. B-012).
- B-008 çözülene kadar işletmeye özgü bilgi commit edilmez ([AGENTS.md](AGENTS.md) §5).
