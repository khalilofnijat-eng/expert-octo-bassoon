# knowledge/

Bilgi tabanının **doğruluk kaynağı veritabanıdır** (`kb_entry`, `business_rule`, `kb_release`); bu klasör kaynak değildir ([../docs/DECISIONS.md](../docs/DECISIONS.md) D-028, [../docs/ARCHITECTURE.md](../docs/ARCHITECTURE.md) §9.4).

- Buraya yalnızca her aktif KB sürümünün **PII içermeyen, salt okunur dökümleri** yazılır (D-008). Döküm elle düzenlenmez; değişiklik yönetim ekranındaki onay ve sürüm sürecinden geçer (D-004, D-005, D-027).
- Kritik kurallar (fiyat politikası, indirim sınırı, garanti, iade, uyumluluk politikası) yalnızca `business_rule` tablosundadır ve KB dökümüne girmez (D-027).
- [../BLOCKERS.md](../BLOCKERS.md) B-008 çözülene kadar işletmeye özgü içerik (kurallar, fiyatlar, tedarikçi/depo bilgileri, KB dökümleri) **commit edilmez** ([../AGENTS.md](../AGENTS.md) §5).

Henüz içerik yok.
