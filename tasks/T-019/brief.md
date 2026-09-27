# T-019 — Output filter (saf fonksiyon)

- **Aşama:** 6 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Geliştirici agent'ı
- **Tarih:** 2026-09-27

## Amaç

Müşteriye gidecek her metin parçasını son hâliyle denetleyen, yan etkisiz bir çıktı filtresi yazmak (D-025, D-037).

## Kapsam
- Dahil: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §7.2 kuralları — rakam/para (`allowed_literals`; yazıyla sayılar en iyi çaba düzeyinde), iletişim bilgisi ve izin listesi dışı URL, platform dışı ödeme, indirim/iade/garanti vaadi, tamamlanma iddiası, parça başına ≤1000 karakter. Girdi: son render edilmiş parçalar + olgu kağıdı. Her ret bir `reason_code` üretir. Sahip düzeltmesi için uyarı modu.
- Hariç: render/bölme, LLM çağrısı, veritabanı.

## Bağımlılıklar
- T-014.

## Dosya sahipliği
- Yazabileceği dosyalar: `app/` ve `tests/` altındaki bu görevin dosyaları; gerekirse `pyproject.toml`/`uv.lock`.
- Dokunmayacağı dosyalar: ortak Markdown kayıtları, `docs/ARCHITECTURE.md`, `docs/OWNER_REQUEST_*`.
- Aynı çalışma ağacında başka agent'lar da commit eder: yalnızca açık yollarla stage ve commit ([AGENTS.md](../../AGENTS.md) §5).

## Beklenen çıktı
- Push edilmiş commit; testler yalnızca sentetik veriyle.
- Teslim raporu: Main Agent'a **metin olarak** (rapor dosyası yok — [BLOCKERS](../../BLOCKERS.md) B-012).

## Kabul ölçütleri
Tam metin: [docs/ARCHITECTURE.md](../../docs/ARCHITECTURE.md) §14, T-019 satırı. Özet:
- [ ] §7.2'deki her kural için kabul ve ret örnekleri; bilinen sınırlar (argo, yazım hatası, başka dillerde sayı kelimeleri) açıkça işaretli.
- [ ] Filtre saf fonksiyondur (G/Ç yok).
- [ ] Sahip düzeltmesinde uyarı modu ve "yine de gönder" için açık onay gerektiren sonuç.
- [ ] **Bağımsız inceleme zorunlu**, T-028 ile birlikte (geliştiren dışında bir agent).
