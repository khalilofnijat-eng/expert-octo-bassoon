# CLAUDE.md — Oto parça e-ticaret sitesi

Bu depo, sahibin oto parça e-ticaret sitesidir. **Ayrı bir projedir**; ileride sahibin Avito müşteri asistanı projesiyle (`khalilofnijat-eng/expert-octo-bassoon`, dal `claude/youthful-goldberg-l427nm`) birleştirilecektir. Ürün, uyumluluk ve stok verisi o projeyle uyumlu tutulur: [KICKOFF_PROMPT.md](KICKOFF_PROMPT.md) bölüm 5.

## Oturum başı okuma sırası

1. Bu dosya.
2. `AGENTS.md` → `STATE.md` → `HANDOFF.md` → `TASKS.md` → `BLOCKERS.md`.
3. Bu kayıtlar henüz yoksa (ilk oturum): [KICKOFF_PROMPT.md](KICKOFF_PROMPT.md) sahibin ilk talimatıdır; ilk iş, bölüm 1.5'teki kayıt düzenini kurdurmaktır.
4. Tekrarlanan işler için skill önerileri: [SKILLS.md](SKILLS.md).

Önceki agent'ların veya arka plan süreçlerinin hâlâ çalıştığını varsayma; gerçek durumu doğrula.

## Çalışma kuralları (özet; ayrıntı `AGENTS.md`'de)

- Sahip yalnızca Main Agent ile, Türkçe konuşur. Main Agent görev dağıtır ve kabul/red eder; uygulama işlerini gerçek alt agent'lar yapar.
- Her görevin brief'i: amaç, kapsam, bağımlılıklar, dosya sahipliği, beklenen çıktı, kabul ölçütleri. Alt agent'lar yalnızca kendi dosyalarına yazar.
- Kritik bileşenler (ödeme, fiyat/ek ücret hesabı, uyumluluk gösterimi, kişisel veri, yönetim paneli yetkilendirmesi, VIN entegrasyonu) geliştirenden farklı bir agent tarafından incelenir.
- Bilgi uydurulmaz. Bilinmeyen "BİLİNMİYOR" yazılır ve `BLOCKERS.md`'ye bağlanır. Sahibe sorular toplu iletilir.
- Kanıtsız uyumluluk iddiası yok; stok kaynağı kapalı veya eskiyse stok iddiası yok; fiyat güncel değilse kesin fiyat yok.
- Sentetik veri işaretlidir (`SYN-` SKU öneki, `data_origin = synthetic`, "SYNTHETIC" filigranı); üretimde reddedilir. Test raporunda sentetik ve gerçek veri sonuçları ayrıdır.
- Akış: tasarım → prototip → bağımsız inceleme ve sahip onayı → yapım. Küçük, doğrulanabilir aşamalar.
- Avito'dan veri kazıma ve Avito müşterilerini platform dışına çekmeye yönelik özellik yapılmaz.

## Gizli bilgiler ve git

- Şifre, API anahtarı, token ve çerez **asla** sohbete, belgeye veya git'e girmez. Yalnızca ortam değişkeni veya git'e girmeyen `.env`; belgelerde yalnızca değişken adı.
- Depo özel (private) olmalıdır. Müşteri verisi, siparişler, veritabanları, gerçek ürün fotoğrafları, maliyet, indirim sınırı ve tedarikçi bilgisi commit edilmez.
- Yalnızca açık dosya yollarıyla stage et (`git add <yol>`); `git add -A` kullanma. Force-push yok.
