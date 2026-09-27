# T-001 — Ortam ve erişim keşfi

- **Aşama:** 1 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** Keşif agent'ı
- **Tarih:** 2026-09-27

## Amaç

Geliştirme ortamının ve deponun doğrulanmış olgularını çıkarmak.

## Kapsam
- Dahil: depo içeriği ve görünürlüğü; çalışma zamanı sürümleri; ağ erişimi (Avito, Avito API, PyPI, npm, Anthropic, GitHub); mevcut tarayıcı / uzak cihaz araçları; kimlik bilgisi ortam değişkenlerinin **yalnızca adları**; "bulutta yapılabilir" ile "sahibin makinesi gerekir" ayrım tablosu.
- Hariç: herhangi bir yazma veya dış sisteme etki eden işlem (görev salt okunurdur); gizli değerlerin okunması/yazılması.

## Bağımlılıklar
- Yok.

## Dosya sahipliği
- Yazabileceği dosya: yok (salt okunur görev).

## Beklenen çıktı

Main Agent'a **metin olarak** teslim raporu ([şablon](../_TEMPLATE/report.md) yapısında). Rapor dosyası beklenmez ([BLOCKERS](../../BLOCKERS.md) B-012).

> Not (T-011, 2026-09-27): Bu brief ilk hâlinde `tasks/T-001/report.md` dosyasını istiyordu; alt agent'ların rapor dosyası yazamadığı anlaşıldıktan sonra B-012 kuralına uyarlandı.

## Kabul ölçütleri
- [ ] Her ifade komut çıktısıyla desteklenir.
- [ ] Hiçbir gizli değer yazılmaz.
