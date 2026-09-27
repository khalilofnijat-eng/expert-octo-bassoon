# app/

Uygulama kodu (Python 3.11 paketi `app`). Mimari taslak: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md); modül adları oradaki bileşenlerle eşleşir. Şu an yalnızca iskelet, ayarlar, `/healthz` ve PII maskeleyici vardır; diğer modüller boş pakettir.

| Yol | İçerik |
|---|---|
| `config.py` | Ayarlar (pydantic-settings): ortam değişkenleri ve commit edilmeyen `.env` dosyası. Değişken adları: [../.env.example](../.env.example). `AUTOMATION_MODE` varsayılanı `draft_only`; `DATA_DIR` depo içini gösterirse başlangıç hata verir. |
| `main.py` | FastAPI uygulaması (`create_app()`). |
| `ops/health.py` | `GET /healthz` — yalnızca sürecin ayakta olduğunu bildirir (DB veya dış sistem kontrol etmez). |
| `safety/masker.py` | Deterministik, regex tabanlı PII maskeleyici: telefon, e-posta, kart (Luhn), VIN, plaka, sosyal hesap/bağlantı, URL → `[PHONE_1]` gibi yer tutucular. Sınırlamaları modülün docstring'inde yazılıdır (ad ve adres yakalanmaz). |
| diğer alt paketler | `avito_gateway`, `ingest`, `conversation`, `inventory`, `catalog`, `offers`, `orders`, `llm`, `knowledge`, `evals`, `admin` — henüz boş. |

## Kurulum ve çalıştırma

Gereken: [uv](https://docs.astral.sh/uv/). Python 3.11'i uv kendisi bulur veya kurar (`.python-version`).

```bash
uv sync                                  # bağımlılıkları uv.lock'tan kurar (.venv/)
cp .env.example .env                     # yalnızca yerelde; .env asla commit edilmez
uv run uvicorn app.main:app --reload     # http://127.0.0.1:8000/healthz
```

Maskeleyici örneği:

```python
from app.safety.masker import mask

mask("Звоните 8 900 000-00-01").text  # 'Звоните [PHONE_1]'
```

`mask(text, keep_mapping=True)` yer tutucu → orijinal eşlemesini de döndürür; bu eşleme yalnızca bellekte tutulur, loglanmaz ve saklanmaz.

## Denetimler

CI ([../.github/workflows/ci.yml](../.github/workflows/ci.yml)) her push'ta aynı komutları çalıştırır:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy app
uv run pytest -q
```
