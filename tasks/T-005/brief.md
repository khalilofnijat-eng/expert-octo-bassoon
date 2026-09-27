# T-005 — Kayıt düzeninin bağımsız incelemesi

- **Aşama:** 2 ([PLAN](../../docs/PLAN.md))
- **Sahip (agent rolü):** İnceleme agent'ı (kayıtları yazan Dokümantasyon agent'ından farklı)
- **Tarih:** 2026-09-27

## Amaç

Kalıcı kayıt düzenini (T-003, T-009) bağımsız olarak, yalnızca okuyarak incelemek.

## Kapsam
- Dahil: tüm Markdown kayıtlarında tutarlılık (aynı olgu farklı yerlerde çelişiyor mu), gereksiz tekrar (tek kaynak ilkesine aykırılık), kırık göreli bağlantılar, uydurulmuş bilgi (kaynağı olmayan işletme/sistem/platform iddiası), gizli değer bulunup bulunmadığı, yeni oturumun kayıtlardan işi sürdürebilirliği.
- Hariç: herhangi bir dosya değişikliği; düzeltmeler ayrı görevle yapılır.

## Bağımlılıklar
- T-009.

## Dosya sahipliği
- Yazabileceği dosya: yok (salt okunur).

## Beklenen çıktı

Main Agent'a **metin olarak** inceleme raporu (rapor dosyası beklenmez — B-012): her bulgu için dosya ve satır, sorun, önerilen düzeltme ve önem derecesi.

## Kabul ölçütleri
- [ ] Her bulgu dosya/satır kanıtıyla verilir.
- [ ] Bağlantı denetimi çalıştırılmış ve çıktısı raporda.
- [ ] Hiçbir dosya değiştirilmemiş (`git status` ile gösterilir).
