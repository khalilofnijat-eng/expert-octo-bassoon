# app/

Uygulama kodu (Python 3.11 paketi `app`). Mimari taslak: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md); modül adları oradaki bileşenlerle eşleşir. Şu an iskelet, ayarlar, `/healthz`, PII maskeleyici ve çekirdek DB/kuyruk katmanı vardır; diğer modüller boş pakettir.

| Yol | İçerik |
|---|---|
| `config.py` | Ayarlar (pydantic-settings): ortam değişkenleri ve commit edilmeyen `.env` dosyası. Değişken adları: [../.env.example](../.env.example). `AUTOMATION_MODE` varsayılanı `draft_only`; `DATA_DIR` depo içini gösterirse başlangıç hata verir. |
| `main.py` | FastAPI uygulaması (`create_app()`). |
| `ops/health.py` | `GET /healthz` — yalnızca sürecin ayakta olduğunu bildirir (DB veya dış sistem kontrol etmez). |
| `safety/masker.py` | Deterministik, regex tabanlı PII maskeleyici: telefon, e-posta, kart (Luhn), VIN, plaka, sosyal hesap/bağlantı, URL → `[PHONE_1]` gibi yer tutucular. Sınırlamaları modülün docstring'inde yazılıdır (ad ve adres yakalanmaz). |
| `db/` | Çekirdek tablolar (SQLAlchemy 2 modelleri, §5), CAS yardımcıları (`cas.py`: genel CAS ve outbox intent CAS), korumalı yazmalar (`writes.py`: mesaj dedup, kilit bağlantısından koşullu taslak INSERT'i, audit ekleme). Migration: `../migrations/`. |
| `queue/` | `job` kuyruğu (`jobs.py`), advisory lock'lar ve singleton (`locks.py`), tek worker döngüsü (`worker.py`). Kurallar ARCHITECTURE §6.1–§6.2. |
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

## Geliştirme veritabanı (PostgreSQL 16)

Çekirdek tablolar Alembic migration'ı ile kurulur (`../alembic.ini`, `../migrations/`). Bağlantı adresi `DATABASE_URL`'den okunur; adres ve şifre dosyalara yazılmaz.

```bash
docker compose -f docker-compose.dev.yml up -d           # yalnızca 127.0.0.1:5432, dev şifresi gizli değildir
export DATABASE_URL=postgresql+psycopg://postgres:dev-only@127.0.0.1:5432/postgres
uv run alembic upgrade head
```

Docker yoksa aynı iş yerel PostgreSQL 16 ikili dosyalarıyla, root olmayan bir kullanıcıyla yapılabilir (ör. `runuser -u postgres -- /usr/lib/postgresql/16/bin/initdb -D <dizin>` ve `pg_ctl ... start`). Veri dizini depo dışında olmalıdır.

**Gerçek DB testleri** (`../tests/db/`): `TEST_DATABASE_URL` bir süper kullanıcıyla PostgreSQL 16'yı göstermelidir. Testler geçici bir veritabanı açar, migration'ı uygular ve sonunda siler; `pg_terminate_backend` kullandıkları için süper kullanıcı gerekir. Değişken yoksa bu testler atlanır; CI'da `REQUIRE_TEST_DATABASE=1` olduğu için atlanmaz, hata verir.

```bash
export TEST_DATABASE_URL=postgresql+psycopg://postgres:dev-only@127.0.0.1:5432/postgres
uv run pytest -q tests/db
```

**Roller.** Migration'ı tablo sahibi olan kullanıcı çalıştırır; bu kullanıcının `CREATEROLE` yetkisi olmalıdır. Migration `assistant_app` (NOLOGIN) rolünü oluşturur: çekirdek tablolarda SELECT/INSERT/UPDATE/DELETE, `audit_event`'te yalnızca SELECT/INSERT hakkı vardır. Uygulamanın giriş kullanıcısı tablo sahibi olmamalı, yalnızca bu rolün üyesi olmalıdır (`GRANT assistant_app TO <giriş_kullanıcısı>`). Ayrıca `audit_event` üzerindeki bir tetikleyici UPDATE/DELETE/TRUNCATE'i tablo sahibi dahil herkese reddeder (süper kullanıcı tetikleyiciyi kapatabilir; bu bilinen sınırdır).

**Tek worker ve kilitler** (ARCHITECTURE §6.1): worker açılışta ayrı bir bağlantıda `(1, 0)` singleton kilidini alır ve bu bağlantıyı `WORKER_SINGLETON_POLL_S` saniyede bir yoklar; bağlantı koparsa süreç `os._exit(75)` ile çıkar. Konuşma işleri `(2, conversation_id)` kilidini havuzdan ayrılmış, tek sahipli bir bağlantıda tutar; kilit alınamazsa iş `done` olmaz, `WORKER_LOCK_BUSY_DELAY_S` sonra yeniden kuyruğa girer.

## Denetimler

CI ([../.github/workflows/ci.yml](../.github/workflows/ci.yml)) her push'ta aynı komutları çalıştırır:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy app
uv run pytest -q
```
