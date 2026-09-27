# sessions/ — Oturum özetleri

Her Main Agent oturumu için bir dosya: `YYYY-MM-DD-SNN.md` (aynı gün birden fazla oturumda `S01`, `S02`…). Özetler kısa tutulur; durum ve kararlar kendi tek kaynaklarına ([../STATE.md](../STATE.md), [../TASKS.md](../TASKS.md), [../docs/DECISIONS.md](../docs/DECISIONS.md), [../BLOCKERS.md](../BLOCKERS.md)) yazılır, burada yalnızca bağlantı verilir.

## Biçim

```markdown
# YYYY-MM-DD-SNN — <kısa başlık>

- **Oturum:** Main Agent oturumu N
- **Tarih:** YYYY-MM-DD

## Olanlar
- ...

## Başlatılan / teslim alınan görevler
- T-NNN ... (bkz. TASKS.md)

## Sahiple iletişim
- Sorulanlar / alınan cevaplar (gizli değer yazılmaz)

## Sonraki adımlar
- ...
```

## Oturumlar

- [2026-09-27-S01](2026-09-27-S01.md) — İlk oturum: talimat, keşif, kayıt düzeni, mimari taslağı ve bağımsız incelemeler.
