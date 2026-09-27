# Windows kurulumu — Avito kimlik bilgileri ve erişim kontrolü

Bu belge, projeyi sahibin Windows bilgisayarına kurmayı ve Avito API anahtarını **güvenli** şekilde girmeyi adım adım anlatır (T-039). Teknik bilgi gerekmez; komutları olduğu gibi kopyalayıp PowerShell penceresine yapıştırmanız yeterlidir.

> **Önce okuyun — üç kural**
> 1. `client_id` ve `client_secret` değerlerini **asla** sohbete (Claude dahil), e-postaya, mesajlaşma uygulamasına veya başka bir dosyaya yapıştırmayın. Yalnızca 4. adımdaki betiğe girin.
> 2. `secrets.env` dosyası **asla** Git'e eklenmez ve kimseyle paylaşılmaz. Dosya bilerek proje klasörünün ve Obsidian kasasının dışında durur.
> 3. Anahtarın sızdığından şüphelenirseniz Avito kişisel kabinetinde anahtarı hemen **iptal edin** ve yenisini oluşturun; sonra 4. adımı yeniden çalıştırın.

## 0. Neye ihtiyacınız var

- Windows 10 veya 11, internet bağlantısı.
- Avito Pro hesabınızın API bilgileri: **client_id** ve **client_secret**. Anahtar şirketin **ana** hesabından olmalıdır (çalışan hesabının anahtarıyla Messenger API eksik çalışır — [BLOCKERS.md](../BLOCKERS.md) B-007). Avito'nun geliştirici sayfası: https://developers.avito.ru (bu adres geliştirme ortamından açılamadı; menü adlarını burada tarif etmiyoruz).
- İsteğe bağlı: Avito **hesap kimliğiniz** (sayısal `user_id`). Bilmiyorsanız sorun değil; erişim kontrolü onu Avito'dan kendisi alır.

Tüm komutlar **PowerShell** penceresinde çalıştırılır: Başlat menüsüne `PowerShell` yazın ve açın.

## 1. Git ve uv'yi kurun

```powershell
winget install Git.Git astral-sh.uv
```

- Kurulum bitince PowerShell penceresini **kapatıp yeniden açın** (yeni programların bulunması için).
- Kontrol: `git --version` ve `uv --version` birer sürüm numarası yazmalı.
- `winget` çalışmazsa resmî sayfalardan kurun:
  - Git: https://git-scm.com/downloads/win
  - uv: https://docs.astral.sh/uv/getting-started/installation/

## 2. Projeyi indirin (clone)

Projeyi koymak istediğiniz klasöre geçin (örnek: Belgeler) ve indirin:

```powershell
cd $HOME\Documents
git clone https://github.com/khalilofnijat-eng/expert-octo-bassoon.git
cd expert-octo-bassoon
git switch claude/youthful-goldberg-l427nm
```

- Son satır, geliştirmenin yapıldığı dalı açar ([docs/DECISIONS.md](DECISIONS.md) D-014). Dal değişirse Main Agent size bildirir.
- **Depo özel (private) yapıldıktan sonra** `git clone` ve `git pull` sırasında GitHub girişi istenir: açılan pencerede/tarayıcıda kendi GitHub hesabınızla giriş yapın. GitHub şifrenizi de sohbete yazmayın.
- Proje klasörünü Obsidian kasanızın **içine** koymayın.

Sonraki tüm komutlar bu proje klasöründe (`expert-octo-bassoon`) çalıştırılır.

## 3. Bağımlılıkları kurun

```powershell
uv sync
```

Gerekirse doğru Python sürümünü de uv kendisi indirir. İlk seferde birkaç dakika sürebilir.

## 4. Avito kimlik bilgilerini girin

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\windows\setup-avito-credentials.ps1
```

- İlk satır, betik çalıştırma iznini **yalnızca bu PowerShell penceresi için** açar; pencere kapanınca eski ayar geri gelir. Bilgisayarın genel ayarı değişmez.
- Betik sırayla sorar:
  1. `client_id` — yazarken/yapıştırırken ekranda **görünmez**. Yapıştırmak için `Ctrl+V` veya farenin sağ tuşu, sonra `Enter`.
  2. `client_secret` — aynı şekilde görünmez.
  3. Hesap kimliği — isteğe bağlı; bilmiyorsanız boş bırakıp `Enter`.
- Değerler şu dosyaya yazılır: `%LOCALAPPDATA%\AvitoAssistant\secrets.env` (genellikle `C:\Users\<kullanıcı adınız>\AppData\Local\AvitoAssistant\secrets.env`).
- Klasörün ve dosyanın izinleri **yalnızca sizin Windows kullanıcınıza** verilir; başka kullanıcılar okuyamaz. İzin kısıtlanamazsa betik dosyayı silip hata verir.
- Betik değerleri hiçbir zaman ekrana yazdırmaz.

**Değiştirmek için:** betiği yeniden çalıştırın. Boş bıraktığınız alan eski değerini korur; hesap kimliğini silmek için `-` yazın.

**Silmek için:**

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\scripts\windows\setup-avito-credentials.ps1 -Remove
```

(Onay için `EVET` yazmanız istenir.)

Not: Dosyayı başka bir yerde tutmak isterseniz `ASSISTANT_SECRETS_FILE` ortam değişkenine tam yolunu yazabilirsiniz. Uygulama, proje klasörünün, başka bir Git klasörünün veya bir Obsidian kasasının içindeki gizli dosyayı **reddeder**.

## 5. Erişimi kontrol edin

Önce isterseniz alıştırma yapın — bu komut Avito'ya **bağlanmaz**, sahte (sentetik) verilerle örnek çıktı gösterir:

```powershell
uv run python scripts/avito_access_check.py --dry-run
uv run python scripts/avito_access_check.py --dry-run --scenario messenger-403
```

Gerçek kontrol:

```powershell
uv run python scripts/avito_access_check.py
```

Bu kontrol Avito'da **hiçbir şeyi değiştirmez**: en fazla 4 okuma isteği yapar (token, hesap bilgisi, 1 ilan, 1 sohbet başlığı), hiçbirini tekrarlamaz, mesaj göndermez ve sohbetleri "okundu" yapmaz. Çıktıda anahtar, token, sohbet kimliği veya mesaj içeriği **yoktur**; hesap kimliğinin yalnızca son 3 hanesi gösterilir. Bu yüzden çıktıyı Main Agent'a kopyalayabilirsiniz.

### Çıktı nasıl okunur

| Satır | Anlamı | Ne yapmalı |
|---|---|---|
| `Gizli dosya: bulundu` | 4. adımdaki dosya okundu. | — |
| `Gizli dosya: yok (ortam/.env)` | Dosya bulunamadı; değerler başka yerden (ortam değişkeni / `.env`) okunuyor olabilir. | 4. adımı çalıştırın. |
| `Token: OK` | client_id / client_secret doğru; Avito giriş belirteci verdi. | — |
| `Token: BAŞARISIZ (HTTP 400/401/403) — yetki reddedildi` | Anahtar yanlış, eksik kopyalanmış veya iptal edilmiş. | 4. adımı yeniden çalıştırıp değerleri dikkatle yapıştırın. |
| `Token: BAŞARISIZ (yanıt yok) — ağ hatası / zaman aşımı` | Avito'ya ulaşılamadı. | İnternet bağlantısını, VPN/güvenlik duvarını kontrol edin. |
| `Hesap kimliği: bulundu (son 3 hane …123)` | Hesap bilgisi alındı. | — |
| `AVITO_USER_ID: … AYNI DEĞİL` | Girdiğiniz hesap kimliği, anahtarın ait olduğu hesapla eşleşmiyor. | 4. adımda hesap kimliğini `-` ile silin veya düzeltin. |
| `Items API erişilebilir: evet (HTTP 200)` | İlan listesi okunabiliyor. | — |
| `Messenger API erişilebilir: evet (HTTP 200)` | Sohbetler okunabiliyor. | — |
| `Messenger API erişilebilir: hayır (HTTP 403 …)` + `403 → muhtemelen tarife kısıtı (hangi tarifenin gerektiği canlı doğrulanmadı)` | Sohbet erişimi reddedildi; en olası neden tarife. Hangi tarifenin yettiği **canlı doğrulanmadı**: spec kopyası "Товары" için «Максимальный» diyor, sizin bilginize göre «Расширенный» yeterli. Ana hesap yerine çalışan hesabının anahtarı kullanılması da Messenger hatalarına yol açar ([INTEGRATIONS.md](INTEGRATIONS.md) §3.2). | Çıktıyı Main Agent'a iletin (B-007). Tarifeyi değiştirdikten sonra kontrolü **yeniden çalıştırın**; karar bu sonuca göre verilir. |
| `hız sınırı (HTTP 429)` | Kısa sürede çok istek yapıldı. | Birkaç dakika bekleyip bir kez daha çalıştırın. |
| `Avito sunucu hatası (HTTP 5xx)` | Avito tarafında geçici sorun. | Daha sonra tekrar deneyin. |
| `Ayar hatası: …` | Kimlik bilgileri eksik veya gizli dosya kabul edilmeyen bir yerde. | Mesajdaki talimatı izleyin (genellikle 4. adım). |

Komutun çıkış kodu: `0` her şey erişilebilir, `1` en az bir kontrol başarısız, `2` ayar hatası.

**Tarife değişikliğinden sonra:** Avito tarifenizi değiştirdiyseniz (ör. «Расширенный» tarifesine geçiş) bu kontrolü yeniden çalıştırın ve çıktıyı Main Agent'a iletin. Messenger API'nin o tarifede açık olup olmadığına belgeler değil, bu kontrolün sonucu karar verir.

**Sonraki adım:** erişim kontrolünden sonra `docs/VAULT_SURVEY.md` belgesindeki adımlara geçin (T-043; belge hazırlanıyor, henüz yoksa Main Agent size haber verir).

## 6. Main Agent'ın bu bilgisayarda çalışması için yerel Claude oturumu

*Aşağıdaki iki yol Main Agent'ın ortam belgelerine göredir; ekran ve menü adları sürüme göre değişebilir, burada yalnızca belgelerde geçen adlar kullanıldı.*

- **Claude Desktop uygulaması:** uygulamanın **Code** özelliğini açın ve çalışma klasörü olarak bu proje klasörünü (`expert-octo-bassoon`) seçin.
- **Terminal:** PowerShell'de proje klasörüne geçip şunu çalıştırın:

  ```powershell
  claude remote-control
  ```

Hangi yolu kullanacağınızı ve bağlantının nasıl tamamlanacağını Main Agent size söyler. Bu oturumda da kurallar aynıdır: anahtarları sohbete yazmayın; Claude'un ihtiyacı olursa değerleri değil yalnızca 5. adımın çıktısını paylaşın.

## 7. Güvenlik özeti

- Anahtarlar yalnızca `%LOCALAPPDATA%\AvitoAssistant\secrets.env` dosyasında, yalnızca sizin kullanıcınızın okuyabileceği şekilde durur.
- Bu dosyayı Git'e eklemeyin, e-postayla göndermeyin, bulut klasörüne (OneDrive vb.) veya Obsidian kasasına kopyalamayın. Proje `.gitignore`'u `*.env` dosyalarını zaten dışarıda tutar.
- Sızıntı şüphesinde: Avito kabinetinde anahtarı iptal edin → yeni anahtar oluşturun → 4. adımı yeniden çalıştırın → 5. adımla kontrol edin → Main Agent'a bildirin.
- Bilgisayardan kaldırmak için: 4. adımdaki `-Remove` komutu.
