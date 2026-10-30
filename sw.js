// Service worker do Informativo Agro: rede primeiro (dados sempre frescos), cache só como reserva offline.
const CACHE = "informativo-agro-v11";
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./logo.svg",
  "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png", "./favicon.png"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).catch(() => {}));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  // nunca intercepta/guarda requisições de outros domínios (ex.: gc.zgo.at, *.goatcounter.com)
  if (req.method !== "GET" || new URL(req.url).origin !== self.location.origin) return;
  e.respondWith(
    fetch(req, {cache: "no-store"}).then(res => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.match(req).then(r => r || (req.mode === "navigate" ? caches.match("./index.html") : undefined))
      .then(r => r || new Response("Sem conexão", {status: 503, headers: {"Content-Type": "text/plain; charset=utf-8"}})))
  );
});
