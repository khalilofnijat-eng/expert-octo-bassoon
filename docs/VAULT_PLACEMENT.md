# Proje klasörünü Obsidian kasasına yerleştirme

Bu belge, proje klasörünü Windows bilgisayarınızdaki Obsidian kasasının (vault) içine `Avito-Assistant` adıyla koymayı anlatır ([DECISIONS.md](DECISIONS.md) D-003). Sonra yerel Claude oturumu bu klasörde açılır ve ilk mesaj olarak [../LOCAL_SESSION_PROMPT.md](../LOCAL_SESSION_PROMPT.md) yapıştırılır.

Komutlar **PowerShell**'de çalıştırılır. Git ve uv kurulumu: [SETUP_WINDOWS.md](SETUP_WINDOWS.md) §1.

## Seçenek A — önerilen: `git clone`

Git geçmişi korunur; yerel oturum doğrudan commit ve push yapabilir.

```powershell
cd "<kasanızın klasörü>"
git clone https://github.com/khalilofnijat-eng/expert-octo-bassoon.git Avito-Assistant
cd Avito-Assistant
git branch --show-current
```

Son komut `claude/youthful-goldberg-l427nm` yazmıyorsa geliştirme dalına geçin:

```powershell
git checkout claude/youthful-goldberg-l427nm
```

Depo özel (private) yapıldıktan sonra GitHub girişi istenir; kendi hesabınızla giriş yapın, şifrenizi sohbete yazmayın.

## Seçenek B — ZIP indirme (daha kötü)

GitHub sayfasından ZIP indirip kasada `Avito-Assistant` klasörüne açabilirsiniz. Ama ZIP'te **Git geçmişi yoktur**: yerel oturum ne commit ne push yapabilir. Oturum önce klasörü yeniden clone etmek ya da `git init` yapıp depoya bağlamak zorunda kalır; bu, dosyaların karışma riskini taşır. Mümkünse Seçenek A'yı kullanın.

## Python ortamını kasanın dışında tutun

`uv` varsayılan olarak proje klasöründe büyük bir `.venv` klasörü açar. Kasada olmasın diye ortamı kasa dışına yönlendirin (bir kez, kalıcı olarak, kullanıcı düzeyinde):

```powershell
[Environment]::SetEnvironmentVariable('UV_PROJECT_ENVIRONMENT', "$env:LOCALAPPDATA\AvitoAssistant\venv", 'User')
```

Ardından PowerShell'i **kapatıp yeniden açın** ve kontrol edin: `$env:UV_PROJECT_ENVIRONMENT` bir yol yazmalı. Bundan sonra `uv sync` ortamı `%LOCALAPPDATA%\AvitoAssistant\venv` altına kurar.

## Gizli değerler ve veri kasada değil

- Avito kimlik bilgileri `%LOCALAPPDATA%\AvitoAssistant\secrets.env` dosyasındadır ([SETUP_WINDOWS.md](SETUP_WINDOWS.md) §4). Uygulama kasanın veya bir Git klasörünün içindeki gizli değer dosyasını reddeder.
- Veritabanı ve canlı veri `DATA_DIR`'de, kasa ve Git dışında durur ([DECISIONS.md](DECISIONS.md) D-008).

## Obsidian ayarları

Obsidian ayarlarınızı biz değiştirmeyiz. İsterseniz kod klasörlerinin aramada ve grafikte görünmemesi için Obsidian'ın kendi "hariç tutulan dosyalar" ayarına şunları ekleyebilirsiniz: `Avito-Assistant/app`, `Avito-Assistant/tests`, `Avito-Assistant/scripts`. Bu ayar sürüme göre genellikle **Ayarlar → Dosyalar ve bağlantılar → Hariç tutulan dosyalar** (İngilizce: *Settings → Files and links → Excluded files*) altında olur; menü adları farklı olabilir.

## Senkronizasyon

Kasanız Obsidian Sync, iCloud, OneDrive vb. ile eşitleniyorsa `Avito-Assistant` klasörü de eşitlenir. Bu sorun değildir: klasörde gizli değer ve müşteri verisi yoktur. Büyük klasörler (Python ortamı, veritabanı, yedekler) kasanın dışında kalmalıdır; yukarıdaki ayar bunu sağlar.

## Vault taraması hakkında not

Vault taraması ([VAULT_SURVEY.md](VAULT_SURVEY.md)) tüm kasayı tarar; `Avito-Assistant` klasörü de rapora girer (içinde uydurma test notları da vardır: `tests/fixtures/synthetic_vault/`). Raporu yorumlarken bu klasör yok sayılır. Rapor dosyası (`--out`) kasanın **dışına** yazılmalıdır.

## Sonra

1. Yerel Claude oturumunu `Avito-Assistant` klasöründe açın ([SETUP_WINDOWS.md](SETUP_WINDOWS.md) §6).
2. İlk mesaj olarak [../LOCAL_SESSION_PROMPT.md](../LOCAL_SESSION_PROMPT.md) dosyasının tamamını yapıştırın.
