/* LY Haber service worker: uygulama kabuğunu saklar, haber verisini önce internetten ister. */
const CACHE = "ly-haber-v1";
const SHELL = [
  "./",
  "index.html",
  "manifest.webmanifest",
  "icons/icon-192.png",
  "icons/icon-512.png",
  "icons/icon-maskable-512.png",
  "icons/apple-touch-icon.png",
  "icons/favicon-64.png"
];

self.addEventListener("install", (e) => {
  e.waitUntil(caches.open(CACHE).then((c) => c.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (e) => {
  e.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (e) => {
  const req = e.request;
  if (req.method !== "GET") return;
  const url = new URL(req.url);

  // Haber verisi: önce internet, olmazsa son kaydedilen
  if (url.origin === location.origin && url.pathname.includes("/data/")) {
    const key = url.origin + url.pathname;
    e.respondWith(
      fetch(req).then((res) => {
        if (res.ok) { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(key, copy)); }
        return res;
      }).catch(() => caches.match(key))
    );
    return;
  }

  // Sayfa açılışı: önce internet, olmazsa kayıtlı kabuk
  if (req.mode === "navigate") {
    e.respondWith(
      fetch(req).then((res) => {
        const copy = res.clone(); caches.open(CACHE).then((c) => c.put("index.html", copy));
        return res;
      }).catch(() => caches.match("index.html"))
    );
    return;
  }

  // Diğer dosyalar (ikon, yazı tipi): kayıtlıdan ver, arkada güncelle
  e.respondWith(
    caches.match(req).then((hit) => {
      const net = fetch(req).then((res) => {
        if (res.ok || res.type === "opaque") { const copy = res.clone(); caches.open(CACHE).then((c) => c.put(req, copy)); }
        return res;
      }).catch(() => hit);
      return hit || net;
    })
  );
});
