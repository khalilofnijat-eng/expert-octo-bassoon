# RUNBOOK — İşletim talimatları

Her bölüm, ilgili bileşen geliştirilip **test edildikten sonra** doldurulur. Pilot çalışma ortamı: sahibin Windows bilgisayarı ([DECISIONS.md](DECISIONS.md) D-045; [../BLOCKERS.md](../BLOCKERS.md) B-004). Kurulum rehberi T-039'da hazırlanıyor ([../TASKS.md](../TASKS.md)).

## Veritabanı rolleri

Kaynak: T-035 (çekirdek tablolar ve rol denetimi); gerekçe ve worker'ın rol denetimi: [../app/README.md](../app/README.md) → "Geliştirme veritabanı". Gerçek üretim makinesinde henüz uygulanmadı.

Migration'ı tablo sahibi olan rol (`CREATEROLE` yetkili) çalıştırır; uygulama ayrı bir LOGIN rolüyle bağlanır. Bu rol `assistant_app` rolünün üyesidir ve tablo sahibi **asla** değildir.

Adımlar (yer tutucular `<...>`; şifre dosyalara yazılmaz, yalnızca makinenin ortamına girilir):

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

## Başlatma
Henüz çalıştırılabilir bileşen yok.

## Durdurma
Henüz çalıştırılabilir bileşen yok.

## Acil durdurma
Henüz çalıştırılabilir bileşen yok. (Hedef: tüm otomatik gönderimleri tek adımda durdurmak — [ARCHITECTURE.md](ARCHITECTURE.md).)

## Yedekleme
Henüz çalıştırılabilir bileşen yok.

## Geri yükleme
Henüz çalıştırılabilir bileşen yok.

## Güncelleme
Henüz çalıştırılabilir bileşen yok.

## Taşıma
Henüz çalıştırılabilir bileşen yok.

## Arıza giderme
Henüz çalıştırılabilir bileşen yok.
