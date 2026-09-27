# tests/

Birim testleri (pytest). Tüm test verisi **sentetiktir**: telefon, e-posta, kart, VIN, plaka, kullanıcı adı ve URL'ler uydurmadır; kart numaraları herkese açık test numaralarıdır, alan adları `example.*` / `пример.рф`'dir. Sentetik veri içeren dosyalar `# SYNTHETIC` yorumuyla başlar. Gerçek müşteri verisi, gerçek ürün fotoğrafı veya gizli değer buraya girmez.

| Dosya | Kapsam |
|---|---|
| `test_masker.py` | PII maskeleyici: pozitif ve negatif örnekler (Kiril, karışık alfabe, OEM parça numarası / kasa kodu / fiyat / yıl koruması), yer tutucu numaralandırması, eşleme. Bilinen sınırlamalar `xfail(strict=True)` olarak işaretlidir; biri düzelirse test kırılır ve docstring güncellenmelidir. |
| `test_config.py` | Ayarlar: varsayılan `draft_only`, ortam değişkeni ve `.env` okuma, gizli değerlerin `repr`'de görünmemesi, depo içi `DATA_DIR` reddi. |
| `test_health.py` | `GET /healthz`. |
| `test_filter.py` | Output filter ([../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §7.2; T-019, T-034): her `reason_code` için ret ve kabul örnekleri, sahip düzeltmesi modu, `measure_part`. Bilinen sınırlamalar `xfail(strict=True)`. |
| `test_filter_t032.py` | T-032 güvenlik incelemesinin tüm yeniden üretimleri, regresyon testi olarak (T-034); veri: `fixtures/filter/t032_cases.json` (etiketli sentetik vakalar). |
| `avito/` | Avito gateway (T-017) ve gönderim istemcisi (T-018): izin listesi (yazan uç yok), yapılandırma, hata sınıfları (tek HTTP denemesi), sayfalama (her zaman sonlanır), ayrıştırma, öncelikli rate limiter (sanal zaman), gizli değerlerin loglara/`repr`'e girmemesi, token yönetimi, gönderim. Ağ yok: spec tabanlı mock ([../scripts/dev/avito_mock/](../scripts/dev/avito_mock/)) ve `fixtures/avito/`. |
| `catalog/` | Catalog/fitment (T-022, T-022b): sentetik veri seti yükleyicisi, fitment kuralları, W213 ön tampon senaryosu; veri: `fixtures/synthetic_catalog/w213_front_bumper.json` (uydurma SKU, fiyat ve fotoğraf anahtarları). |
| `inventory/` | Inventory portu sözleşmesi sentetik adaptörde (köken, hata modları, iddialar) ve migration 0002 gerçek PostgreSQL'de (`test_inventory_db.py`). |
| `db/` | Gerçek PostgreSQL 16 üzerinde çekirdek tablolar (T-015, T-035): migration, kuyruk, advisory lock'lar ve tek worker, korumalı yazmalar ve CAS, gerçek süreç çökmesi (SIGKILL; `child_worker.py`). |

## Çalıştırma

```bash
uv sync
uv run pytest -q                              # tüm testler
uv run pytest -q tests/test_masker.py         # yalnızca maskeleyici
uv run pytest -q -k plate                     # ada göre filtre
```

**Gerçek PostgreSQL testleri** (`db/`, `inventory/test_inventory_db.py`): `TEST_DATABASE_URL` süper kullanıcılı bir PostgreSQL 16 sunucusunu göstermelidir (testler geçici veritabanı açıp siler). Değişken yoksa bu testler atlanır; `REQUIRE_TEST_DATABASE=1` iken (CI'da öyle) atlanmaz, hata verir. Kurulum ve örnek komut: [../app/README.md](../app/README.md) → "Geliştirme veritabanı". Adres ve şifre dosyalara yazılmaz.

```bash
export TEST_DATABASE_URL=postgresql+psycopg://<kullanıcı>:<şifre>@127.0.0.1:5432/postgres
uv run pytest -q tests/db tests/inventory
```

Çalışma modu `APP_ENV`'den okunur; boş veya bilinmeyen değer üretim sayılır ([../.env.example](../.env.example)). Üretimde sentetik inventory adaptörü başlamaz; `synthetic_fixture` kanıtı yalnızca `test` modunda sayılır ([../app/catalog/runtime.py](../app/catalog/runtime.py)). Catalog/inventory testleri modu açıkça (`RuntimeMode.TEST` vb.) verir.

İleride eklenecek sabit değerlendirme (eval) senaryoları da burada, sentetik ve maskeli olarak tutulur ([../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §9.3). Sonuçlar [../docs/TEST_REPORT.md](../docs/TEST_REPORT.md)'ye yazılır; sentetik ve gerçek sistem testleri ayrı raporlanır.
