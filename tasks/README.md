# tasks/ — Alt agent görev kayıtları ve teslimleri

Her görevin bir klasörü vardır: `tasks/T-NNN/`.

| Dosya | Yazan | İçerik |
|---|---|---|
| `brief.md` | Main Agent (veya onun adına Dokümantasyon agent'ı) | Amaç, kapsam, bağımlılıklar, dosya sahipliği, beklenen çıktı, kabul ölçütleri |
| `report.md` | Görevi yapan alt agent | Yapılan iş, değişen dosyalar, doğrulama kanıtı, kalan sorunlar, Main Agent'a sorular, sonraki somut adım |

Şablonlar: [_TEMPLATE/brief.md](_TEMPLATE/brief.md), [_TEMPLATE/report.md](_TEMPLATE/report.md). Yaşam döngüsü ve kurallar: [../AGENTS.md](../AGENTS.md) §3–4. Görev durumu yalnızca [../TASKS.md](../TASKS.md)'de tutulur; brief ve raporlarda durum tekrarlanmaz.

Kurallar:
- Alt agent yalnızca brief'te kendisine verilen dosyalara yazar.
- Raporlarda gizli değer (şifre, token, çerez, anahtar) ve gereksiz kişisel veri bulunmaz.
- Sahibe soru doğrudan sorulmaz; raporun "Sorular (Main Agent'a)" bölümüne yazılır.
