# HANDOFF — Yeni oturum için devam özeti

**Son güncelleme:** 2026-09-27 (T-036)

Okuma sırası ve kurallar: [AGENTS.md](AGENTS.md) §1. Mevcut durum: [STATE.md](STATE.md). Görev durumları ve bağımlılıklar yalnızca [TASKS.md](TASKS.md)'de; engeller ve sahip cevapları yalnızca [BLOCKERS.md](BLOCKERS.md)'de.

## Nerede kaldık

Mimari rev.2 sahip onayıyla commit edildi (`1f7c2dc`, B-013 çözüldü). Uygulama dalgasından T-015, T-017, T-019, T-022, T-022b, T-018c ve T-035 kabul edildi; bağımsız incelemeler T-032 ve T-033 düzeltmelerle kabul edildi. Hepsi yalnızca sentetik veriyle test edildi ([docs/TEST_REPORT.md](docs/TEST_REPORT.md)). Sahip ödeme yöntemlerini cevapladı (D-039). Main Agent sistemin Avito moderasyonunu atlatmayacağına (D-040), web sitesinin ayrı proje olduğuna (D-041) ve Messenger API tarifesi için sahibe üç seçenek sunulacağına (D-042) karar verdi. T-037 araştırması kabul edildi ([docs/NOTES.md](docs/NOTES.md) → "T-037 bulguları"). Dış sistem bağlantısı yok.

## Sıradaki eylemler

1. **Sahip cevapları:** B-002 (en büyük engel), B-004, B-005'in kalanı (rezervasyon, teslimat, iade/garanti, insana devir, doğrulama rozeti, engel/uyarı geçmişi), B-008, B-012. poisk.vin (B-015) ve Avito desteği mektuplarını sahip gönderir (taslaklar T-040). Cevap geldikçe BLOCKERS'ı ve bağlı görevleri güncellettir.
2. **Sürmekte olanlar:** T-018 ve T-034 (dalda commit'leri var, teslim/kabul kararı kayıtta yok), T-018b (durumu kayıtta yok), T-033b (T-035 doğrulaması), T-039 (Windows yerel kurulum ve salt okunur erişim kontrolü), T-040 (mektuplar). Gerçekten çalışıp çalışmadıklarını doğrula. T-016 ve T-036 teslimlerini değerlendir.
3. **D-042:** üç seçeneği sahibe sun; T-039 erişim kontrolünün sonucunu bekle.
4. **Takip kod görevi (ID atanmadı):** filtrenin nakit için `PAYMENT_TERMS_UNCONFIRMED` reddini gevşet (D-039).
5. **Engelsiz sentetik görevler** (bağımlılıkları kabul edildi): T-020, T-021, T-026. T-025 T-018'i bekler. T-010 B-007, B-009, B-011'i bekler.

## Uyarılar

- Önceki agent'ların veya arka plan süreçlerinin hâlâ çalıştığını varsayma; sürmekte görünen görevlerin gerçek durumunu kontrol et.
- Konteyner geçicidir: push edilmemiş iş kaybolur.
- Aynı çalışma ağacında birden fazla agent commit ediyor: yalnızca açık yollarla stage; ortak dosya başka agent'ın işiyle kirliyse ayrı index (`GIT_INDEX_FILE`) kullan. `.git/index.lock` silinmez.
- Alt agent'lar rapor dosyası yazamaz; brief'lerde rapor dosyası isteme, teslimi metin olarak al (bkz. B-012).
- B-008 çözülene kadar işletmeye özgü bilgi commit edilmez ([AGENTS.md](AGENTS.md) §5); istisna: müşteriye açık ödeme yöntemleri (D-039).
- Kodda karar kimliği yer tutucuları var (`app/safety/filter.py`: "D-k", "D-l"); DECISIONS'ta karşılıkları yok — Main Agent'a soruldu (T-036 teslim metni).
