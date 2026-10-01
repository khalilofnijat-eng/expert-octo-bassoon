# scripts/

Yardımcı betikler. Betikler gizli değer içermez; gerekli değerleri yapılandırmadan (ortam, `.env`, depo dışındaki gizli değer dosyası) okur.

| Yol | Ne yapar | Belge |
|---|---|---|
| `windows/setup-avito-credentials.ps1` | Avito kimlik bilgilerini gizli girişle depo ve Vault dışındaki `%LOCALAPPDATA%\AvitoAssistant\secrets.env` dosyasına yazar (T-039). | [../docs/SETUP_WINDOWS.md](../docs/SETUP_WINDOWS.md) |
| `avito_access_check.py` | Salt okunur Avito erişim kontrolü: token, hesap, ilan ve Messenger için en fazla birer GET; yazma yok (T-039). `--dry-run` mock üzerinde çalışır. | [../docs/SETUP_WINDOWS.md](../docs/SETUP_WINDOWS.md) §5 |
| `vault_survey.py` | Obsidian Vault'un salt okunur, anonimleştirilmiş yapı taraması; değer içermeyen rapor (T-043). | [../docs/VAULT_SURVEY.md](../docs/VAULT_SURVEY.md) |
| `dev/avito_mock/` | Testler için spec tabanlı Avito mock'u (T-017). | [../tests/README.md](../tests/README.md) |
