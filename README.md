# LY Haber

Kişisel haber uygulaması: Türkiye, dünya, ekonomi, finans, spor, kripto ve lastik & filo gündemi tek ekranda.

## Nasıl çalışır

| Ne | Ne zaman | Nereden |
| --- | --- | --- |
| Seçilmiş haberler, manşet, "Bir bakışta", "Bizim için" notları | Her gün 08:45, 12:45, 18:45 | Claude zamanlanmış görevi → `data/haber.json` |
| Son dakika başlıkları ve piyasa şeridi | Yaklaşık 30 dakikada bir | GitHub Actions → `scripts/canli.py` → `data/canli.json` |

## Dosyalar

- `index.html`: uygulamanın kendisi
- `manifest.webmanifest`, `sw.js`, `icons/`: telefona yükleme ve çevrimdışı açılma
- `data/haber.json`: günün seçkisi
- `data/canli.json`: son dakika ve piyasa verisi
- `scripts/canli.py`: RSS ve piyasa verisi toplayıcı (yalnızca Python standart kütüphanesi)
- `.github/workflows/canli.yml`: 30 dakikalık otomatik çalışma

## Telefona yükleme

Siteyi Android'de Chrome ile açın. Üstteki **Yükle** düğmesine ya da Chrome menüsündeki **Uygulamayı yükle** seçeneğine basın.
