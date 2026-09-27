# HANDOFF — Yeni oturum için devam özeti

**Son güncelleme:** 2026-09-27 (T-013)

Okuma sırası ve kurallar: [AGENTS.md](AGENTS.md) §1. Mevcut durum: [STATE.md](STATE.md). Görev durumları ve bağımlılıklar yalnızca [TASKS.md](TASKS.md)'de; engeller ve sahip cevapları yalnızca [BLOCKERS.md](BLOCKERS.md)'de.

## Nerede kaldık

Keşif tamamlandı ve kayıtlara işlendi ([docs/INTEGRATIONS.md](docs/INTEGRATIONS.md)). Mimari taslağı commit edildi ve bağımsız incelemede. Kayıt düzeni incelemesinin düzeltmeleri teslim edildi. Uygulama kodu ve dış sistem bağlantısı yok; sahipten hiçbir engel için cevap gelmedi.

## Sıradaki eylemler

1. T-012 (mimari taslağının bağımsız incelemesi) teslimini değerlendir; durumunu [TASKS.md](TASKS.md)'den ve gerçekte çalışıp çalışmadığını kontrol ederek doğrula.
2. Mimari hakkında karar ver; onaylanan kararları Dokümantasyon agent'ına D-015'ten itibaren kaydettir ve TASKS'ı güncellettir.
3. Uygulama dalgasını T-014'ten başlayan görevlerle planla. Engelsiz işler (sahip verisi ve Avito erişimi gerektirmeyenler) sahip cevaplarını beklemeden yürüyebilir (talep §13; örnek veriyle yapılan iş açıkça işaretlenir — AGENTS §6); engelli görevler ve bağımlılıkları: [TASKS.md](TASKS.md).
4. Sahip cevapları geldikçe [BLOCKERS.md](BLOCKERS.md)'yi ve bağlı görevleri güncellettir.

## Uyarılar

- Önceki agent'ların veya arka plan süreçlerinin hâlâ çalıştığını varsayma; sürmekte görünen görevlerin gerçek durumunu kontrol et.
- Konteyner geçicidir: push edilmemiş iş kaybolur. Metin teslimlerinin kalıcı kaydı: bkz. B-012.
- Alt agent'lar rapor dosyası yazamaz; brief'lerde rapor dosyası isteme, teslimi metin olarak al (bkz. B-012).
- B-008 çözülene kadar işletmeye özgü bilgi commit edilmez ([AGENTS.md](AGENTS.md) §5).
