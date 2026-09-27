# tasks/ — Alt agent görev kayıtları ve teslimleri

Her görevin bir klasörü vardır: `tasks/T-NNN/`.

| Kayıt | Yazan | İçerik |
|---|---|---|
| `brief.md` (dosya) | Main Agent (veya onun adına Dokümantasyon agent'ı) | Amaç, kapsam, bağımlılıklar, dosya sahipliği, beklenen çıktı, kabul ölçütleri |
| Teslim raporu (**metin**, dosya değil) | Görevi yapan alt agent, Main Agent'a | Yapılan iş, değişen dosyalar, doğrulama kanıtı, kalan sorunlar, Main Agent'a sorular, sonraki somut adım |

Şablonlar: [_TEMPLATE/brief.md](_TEMPLATE/brief.md), [_TEMPLATE/report.md](_TEMPLATE/report.md) (teslim metninin yapısı). Yaşam döngüsü ve kurallar: [../AGENTS.md](../AGENTS.md) §3–4. Görev durumu yalnızca [../TASKS.md](../TASKS.md)'de tutulur; brief ve raporlarda durum tekrarlanmaz.

Kurallar:
- Alt agent yalnızca brief'te kendisine verilen dosyalara yazar.
- Teslim raporu Main Agent'a metin olarak verilir. Sahip [../BLOCKERS.md](../BLOCKERS.md) B-012 hakkında karar verene kadar rapor diske yazılmaz (kabuk komutu veya başka geçici çözümle de); kabul edilen bulgular Dokümantasyon agent'ı tarafından ilgili kayıtlara işlenir.
- Raporlarda gizli değer (şifre, token, çerez, anahtar) ve gereksiz kişisel veri bulunmaz.
- Sahibe soru doğrudan sorulmaz; raporun "Sorular (Main Agent'a)" bölümüne yazılır.
- Mevcut istisna: [T-003/report.md](T-003/report.md), kısıt bilinmeden önce yazıldı ve Main Agent tarafından olduğu gibi kabul edildi.
