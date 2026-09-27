# SYNTHETIC Obsidian vault (T-043)

Everything under `vault/` is **made up** for `tests/tools/test_vault_survey.py`: SKUs (`SYN-…`),
OEM-shaped codes, prices, quantities, locations and titles are invented and describe no real
stock. `vault/Запчасти/Фары/SYN-LMP-0003.md` starts with a **UTF-8 BOM**;
`SYN-LMP-0002.md` is committed as UTF-8 (ruff reads `.md` files) and the test re-encodes the
vault copy to **cp1251**.

Created by the test at runtime (not committed): `.obsidian/` (gitignored, must be skipped),
placeholder image files (photos are never committed), and symlinks that escape the vault.
