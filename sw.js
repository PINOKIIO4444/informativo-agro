// Service worker do AgroN (v22): rede primeiro (dados sempre frescos), cache só como reserva offline + alertas push.
const CACHE = "informativo-agro-v22";
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./logo.svg",
  "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png", "./favicon.png", "./badge-96.png"];
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
// v22: alerta enviado pelo computador do Informativo (alerts.py). Conteúdo: {title, body, url, tag}.
self.addEventListener("push", e => {
  let m = {};
  try { m = e.data ? e.data.json() : {}; } catch (_) { m = {body: e.data ? e.data.text() : ""}; }
  const url = new URL(m.url || "./", self.registration.scope);
  // só abre páginas do próprio AgroN
  const safe = url.origin === self.location.origin ? url.href : self.registration.scope;
  e.waitUntil(self.registration.showNotification(m.title || "AgroN", {
    body: m.body || "", icon: "icon-192.png", badge: "badge-96.png", tag: m.tag || "agron",
    renotify: true, data: {url: safe}, lang: "pt-BR"
  }));
});
// toque na notificação: abre (ou traz para frente) o AgroN já na cotação certa (?p=...#chave)
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const target = new URL((e.notification.data && e.notification.data.url) || "./", self.registration.scope).href;
  e.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true}).then(cs => {
    for (const c of cs) {
      if (new URL(c.url).origin === self.location.origin && "navigate" in c) {
        return c.navigate(target).then(w => (w || c).focus()).catch(() => self.clients.openWindow(target));
      }
    }
    return self.clients.openWindow(target);
  }));
});
