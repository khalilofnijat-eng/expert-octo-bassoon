# app/

Uygulama kodu (Python 3.11 paketi `app`). Mimari taslak: [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md); modül adları oradaki bileşenlerle eşleşir. Şu an iskelet, ayarlar, `/healthz`, PII maskeleyici ve çekirdek DB/kuyruk katmanı vardır; diğer modüller boş pakettir.

| Yol | İçerik |
|---|---|
| `config.py` | Ayarlar (pydantic-settings): ortam değişkenleri ve commit edilmeyen `.env` dosyası. Değişken adları: [../.env.example](../.env.example). `AUTOMATION_MODE` varsayılanı `draft_only`; `DATA_DIR` depo içini gösterirse başlangıç hata verir. |
| `main.py` | FastAPI uygulaması (`create_app()`). |
| `ops/health.py` | `GET /healthz` — yalnızca sürecin ayakta olduğunu bildirir (DB veya dış sistem kontrol etmez). |
| `safety/masker.py` | Deterministik, regex tabanlı PII maskeleyici: telefon, e-posta, kart (Luhn), VIN, plaka, sosyal hesap/bağlantı, URL → `[PHONE_1]` gibi yer tutucular. Sınırlamaları modülün docstring'inde yazılıdır (ad ve adres yakalanmaz). |
| `db/` | Çekirdek tablolar (SQLAlchemy 2 modelleri, §5), CAS yardımcıları (`cas.py`: genel CAS ve outbox intent CAS), korumalı yazmalar (`writes.py`: mesaj dedup, kilit bağlantısından koşullu ve idempotent taslak INSERT'i), audit ve uyarı satırları (`audit.py`), `system_setting` değişiklikleri ve geri yükleme kancası (`settings.py`), çalışma rolü denetimi (`roles.py`). Migration: `../migrations/`. |
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

**Roller (üretim kararı).** Migration'ı tablo sahibi olan rol çalıştırır; bu rolün `CREATEROLE` yetkisi olmalıdır. Uygulama **ayrı bir LOGIN rolüyle** bağlanır. Bu rol `assistant_app` rolünün üyesidir ve tablo sahibi **asla** değildir. Migration `assistant_app` (NOLOGIN) rolünü oluşturur: çekirdek tablolarda SELECT/INSERT/UPDATE/DELETE, `audit_event`'te yalnızca SELECT/INSERT hakkı vardır. `audit_event` üzerindeki tetikleyici UPDATE/DELETE/TRUNCATE'i reddeder, ancak tetikleyiciyi **tablo sahibi de** (yalnızca süper kullanıcı değil) kapatabilir. Bu yüzden asıl koruma uygulamanın sahip olmayan bir rolle bağlanmasıdır. `APP_ENV=production` iken (değişken boşsa veya bilinmiyorsa da üretim sayılır) worker, bağlı rol `audit_event`'in sahibiyse, sahip rolüne üyeyse veya süper kullanıcıysa başlamayı reddeder. Aynı modda 0001'in downgrade'i de reddedilir.

Adımlar (yer tutucular `<...>`; şifre dosyalara yazılmaz, yalnızca makinenin ortamına girilir). Dokümantasyon agent'ı bunları RUNBOOK'a taşıyacak:

```sql
-- süper kullanıcı olarak, bir kez:
CREATE ROLE <sahip_rol> LOGIN CREATEROLE PASSWORD '<ortamdan>';
CREATE DATABASE <db> OWNER <sahip_rol>;
CREATE ROLE <uygulama_rol> LOGIN PASSWORD '<ortamdan>' NOSUPERUSER NOCREATEDB NOCREATEROLE;
```

```bash
# sahip rolüyle: tabloları ve assistant_app rolünü kurar
DATABASE_URL=postgresql+psycopg://<sahip_rol>:<...>@<host>/<db> uv run alembic upgrade head
```

```sql
-- sahip rolüyle (CREATEROLE ile oluşturduğu role üye ekleyebilir):
GRANT assistant_app TO <uygulama_rol>;
```

Uygulamanın `DATABASE_URL`'i `<uygulama_rol>`'ü kullanır. Kontrol: `<uygulama_rol>` ile `ALTER TABLE audit_event DISABLE TRIGGER USER` "must be owner" hatası vermelidir.

**Tek worker ve kilitler** (ARCHITECTURE §6.1): worker açılışta ayrı, TCP keepalive ve `tcp_user_timeout` ayarlı bir bağlantıda `(1, 0)` singleton kilidini alır ve `worker_singleton.epoch` değerini bir artırır. Bu bağlantıyı `WORKER_SINGLETON_POLL_S` saniyede bir yoklar (watchdog varsayılan olarak açıktır). Her yoklamanın aynı süre kadar kesin bir zaman sınırı vardır. Bağlantı koparsa, kilit bu oturumda değilse, epoch değiştiyse veya yoklama zamanında cevap vermezse süreç `os._exit(75)` ile çıkar. Yeni worker singleton'ı aldıktan sonra kurtarmadan önce `2 × WORKER_SINGLETON_POLL_S` bekler. İş alma (claim), intent CAS ve hold, singleton'ı pid **ve** epoch ile doğrular (fencing); kilidi kaybetmiş eski worker iş alamaz. Singleton'ı olmayan worker `run_once` çalıştırmaz. Konuşma işleri `(2, conversation_id)` kilidini havuzdan ayrılmış, tek sahipli bir bağlantıda tutar; kilit alınamazsa iş `done` olmaz, deneme sayılmaz, `WORKER_LOCK_BUSY_DELAY_S` sonra yeniden kuyruğa girer.

**Kuyruk sayaçları** (`queue/jobs.py`): `attempts` iş alınırken artar; böylece worker'ı öldüren "zehirli" iş de sayılır. Açılış kurtarması yetim işi geri çekilmeyle yeniden kuyruğa alır; `max_attempts` (varsayılan 12) dolmuşsa iş `dead` olur. `dead` olan her iş `audit_event`'e bir uyarı satırı (`result = 'alert'`) yazar; `requeue_dead` işi sıfır denemeyle geri getirir (yönetim ekranı için). Geri çekilme 10 sn'den 1 saate çıkar; ilk hatadan `dead` olana kadar yaklaşık 1,7–3,4 saat geçer. LLM kesintisi `fail` ile değil `defer` ile işlenir: deneme sayılmaz, `run_after` ertelenir. `enqueue` aynı anahtarlı bekleyen işin `run_after` değerini öne çeker (`LEAST`), ama iş bir hatadan sonra bekliyorsa (`last_error_code` dolu) dokunmaz ve `None` döner.

**Ayarlar** (`db/settings.py`): `system_setting` tek doğruluk kaynağıdır. `AUTOMATION_MODE` ortam değeri yalnızca ilk migration'da satırı doldurur. Satır `kill_switch = true` ile başlar. Kill switch açılınca veya gönderimsiz bir moda geçilince bekleyen outbox parçaları iptal edilir; parça 1'i başlamış grubun konuşması `paused(group_incomplete)` olur. Yedekten geri yüklemeden sonra `force_kill_switch_after_restore` çağrılır (T-031).

## Denetimler

CI ([../.github/workflows/ci.yml](../.github/workflows/ci.yml)) her push'ta aynı komutları çalıştırır:

```bash
uv run ruff check
uv run ruff format --check
uv run mypy app
uv run pytest -q
```
