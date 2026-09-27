# Obsidian kasası yapı taraması (T-043)

Deponuz, stoklarınız, fiyatlarınız ve ürün fotoğraflarınız Obsidian kasanızda duruyor. Asistanın bu bilgiyi okuyabilmesi için önce kasanın **yapısını** öğrenmemiz gerekiyor: hangi klasörler var, notlarda hangi alanlar kullanılıyor, fotoğraflar nerede, bir ürün neyle tanımlanıyor. `scripts/vault_survey.py` betiği bunu çıkarır ve **hiçbir değer içermeyen** bir rapor üretir. Main Agent, envanter bağlantısını bu rapora göre tasarlar; işletme verinizi görmez.

## Betik ne yapar, ne yapmaz

- **Yalnızca okur.** Kasadaki hiçbir dosyayı değiştirmez, silmez, taşımaz; kasanın içine dosya yazmaz. Dosyalar yalnızca okuma kipinde açılır.
- `.obsidian` ayar klasörüne ve diğer gizli klasörlere **hiç girmez**.
- Kısayolları, sembolik bağlantıları ve "junction" klasörlerini **izlemez**; kasanın dışına çıkmaz.
- Raporu kasanın içine yazmayı **reddeder**.
- İnternete bağlanmaz; hiçbir yere bir şey göndermez. Raporu siz paylaşırsınız.
- Kasanız OneDrive gibi bir bulut klasöründeyse, yalnızca bilgisayarda olmayan notlar okunurken bilgisayara indirilebilir. Fotoğraflar okunmaz, yalnızca boyutlarına bakılır.

## Raporda neler var, neler yok

**Var:**
- Klasör ağacı (klasör adlarıyla, varsayılan 3 seviye), her klasördeki not ve ek dosya sayısı
- Ek dosya türleri (`.jpg`, `.png`, `.pdf` …), adetleri ve boyut aralıkları
- Frontmatter/Properties **alan adları**: kaç notta geçtiği, doluluk oranı, türü (sayı, para, tarih, liste, metin, evet/hayır, görsel, kod …)
- Dataview satır içi alanlarının (`anahtar:: değer`) **adları**
- Tablo **sütun adları** ve sütun türleri, tekrar eden şablon başlıkları
- Hangi notların aynı şablonu kullandığı
- Görsellerin notlara nasıl bağlandığı (oranlar)
- Parça/OEM numarası gibi görünen alanlar, ama yalnızca **biçimleri**: ör. `A###-###-##-##` (A = Latin harf, Я = Kiril harf, # = rakam)
- `.csv`, `.base` (Bases), `.canvas` dosyalarının sayısı ve Dataview kullanımı

**Yok:** fiyat, adet, parça/OEM numarası, ürün adı, müşteri adı, not içeriği, dosya adları, kasanızın bilgisayardaki yolu. Değere benzeyen bir alan veya klasör adı (ör. içinde 4 veya daha fazla rakam varsa) de yalnızca biçimiyle gösterilir. Yalnızca bir iki notta geçen başlıklar gösterilmez, çünkü bunlar ürün adı olabilir.

Klasör adlarınız da görünmesin isterseniz `--redact-names` ekleyin. Bu durumda klasör ve başlık adları `K-3fa9c2` gibi anlamsız kodlarla değiştirilir.

## Nasıl çalıştırılır

Önce [SETUP_WINDOWS.md](SETUP_WINDOWS.md) adımları (1–3) yapılmış olmalıdır: proje indirilmiş ve `uv sync` çalıştırılmış olmalı.

### 1. Kasanın yolunu bulun

Obsidian'da kasa değiştirici menüyü açın. Bu menü sol alt köşede kasanın adının yazdığı yerdedir; sürüme göre adı "Kasayı yönet", "Manage vaults" veya "Открыть другое хранилище" olabilir. Listede kasanızın yanında klasör yolu yazar. Başka bir yol da Obsidian'da herhangi bir notun veya klasörün üstüne sağ tıklayıp "Sistem gezgininde göster" / "Show in system explorer" seçeneğini kullanmaktır. Açılan Windows Gezgini penceresinde adres çubuğuna tıklayınca yolu görür ve kopyalayabilirsiniz (ör. `C:\Users\<adınız>\Documents\Kasa`). Menü adları sürüme göre farklı olabilir.

Kasanın yolu, **`.obsidian` klasörünü içeren** klasörün yoludur.

### 2. Betiği çalıştırın

PowerShell'i açın, proje klasörüne geçin ve şunu çalıştırın (yolu kendi kasanızınkiyle değiştirin; tırnaklar kalmalı):

```powershell
cd $HOME\Documents\expert-octo-bassoon
uv run python scripts/vault_survey.py "C:\Users\<adınız>\Documents\Kasa" --out "$HOME\Desktop\kasa_raporu.md"
```

- Rapor masaüstünüzde `kasa_raporu.md` dosyası olarak oluşur. `--out` verilmezse rapor ekrana yazılır. Türkçe karakterler bazı PowerShell pencerelerinde bozuk görünebildiği için dosyaya yazmanızı öneririz.
- `--out` kasanın **dışında** bir yer olmalıdır. Kasanın içini gösterirseniz betik hata verir ve hiçbir şey yazmaz.
- Büyük kasalarda ilerleme alt satırda gösterilir (`[vault_survey] okunuyor: 1250/4000 dosya`). Varsayılan olarak en fazla 50 000 dosya taranır. Rapor "KISMİ" diyorsa `--max-files 200000` ekleyin.

İsteğe bağlı ayarlar:

| Ayar | Anlamı |
|---|---|
| `--redact-names` | Klasör ve başlık adlarını anlamsız kodlarla değiştirir |
| `--depth 4` | Klasör ağacını 4 seviye gösterir (varsayılan 3) |
| `--max-files N` | En fazla N dosya tarar |
| `--quiet` | İlerleme satırını gizler |

### 3. Raporu paylaşın

1. `kasa_raporu.md` dosyasını Not Defteri ile açın ve göz atın. Değer (fiyat, numara, isim) görürseniz göndermeyin; Main Agent'a haber verin.
2. İçeriği kopyalayıp sohbette **Main Agent'a** yapıştırın. Bilgisayarınızda yerel bir Claude oturumu çalışıyorsa ona "masaüstündeki `kasa_raporu.md` dosyasını oku" demeniz de yeterlidir.

## Sonra ne olacak

Main Agent raporu okuyup envanter bağlantısını (salt okunur kasa adaptörünü) tasarlar. Gerekirse size birkaç soru sorar (ör. "stok adedi hangi alanda?"). Kasanızda bir şey değiştirmeniz istenmez. Sizin izniniz olmadan kasanıza hiçbir şey yazılmaz ([AGENTS.md](../AGENTS.md), sahip kuralları).

Geliştiriciler için: testler `tests/tools/test_vault_survey.py`, sentetik kasa `tests/fixtures/synthetic_vault/`.
