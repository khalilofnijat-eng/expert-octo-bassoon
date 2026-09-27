# tests/

Birim testleri (pytest). Tüm test verisi **sentetiktir**: telefon, e-posta, kart, VIN, plaka, kullanıcı adı ve URL'ler uydurmadır; kart numaraları herkese açık test numaralarıdır, alan adları `example.*` / `пример.рф`'dir. Sentetik veri içeren dosyalar `# SYNTHETIC` yorumuyla başlar. Gerçek müşteri verisi, gerçek ürün fotoğrafı veya gizli değer buraya girmez.

| Dosya | Kapsam |
|---|---|
| `test_masker.py` | PII maskeleyici: pozitif ve negatif örnekler (Kiril, karışık alfabe, OEM parça numarası / kasa kodu / fiyat / yıl koruması), yer tutucu numaralandırması, eşleme. Bilinen sınırlamalar `xfail(strict=True)` olarak işaretlidir; biri düzelirse test kırılır ve docstring güncellenmelidir. |
| `test_config.py` | Ayarlar: varsayılan `draft_only`, ortam değişkeni ve `.env` okuma, gizli değerlerin `repr`'de görünmemesi, depo içi `DATA_DIR` reddi. |
| `test_health.py` | `GET /healthz`. |

## Çalıştırma

```bash
uv sync
uv run pytest -q                              # tüm testler
uv run pytest -q tests/test_masker.py         # yalnızca maskeleyici
uv run pytest -q -k plate                     # ada göre filtre
```

İleride eklenecek sabit değerlendirme (eval) senaryoları da burada, sentetik ve maskeli olarak tutulur ([../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §9.3). Sonuçlar [../docs/TEST_REPORT.md](../docs/TEST_REPORT.md)'ye yazılır; sentetik ve gerçek sistem testleri ayrı raporlanır.
