// Service worker do AgroN (v26): rede primeiro (dados sempre frescos), cache só como reserva offline + alertas push.
// v26: isolado de outros projetos na mesma origem (pinokiio4444.github.io): só mexe nos próprios caches
// ("informativo-agro-*"), só atende requisições dentro do próprio escopo e só foca/abre abas do próprio escopo.
const PREFIX = "informativo-agro-";
const CACHE = PREFIX + "v26";
const SCOPE = self.registration.scope;              // ex.: https://pinokiio4444.github.io/informativo-agro/
const inScope = u => { try { return new URL(u, SCOPE).href.startsWith(SCOPE); } catch (_) { return false; } };
const CORE = ["./", "./index.html", "./manifest.webmanifest", "./logo.svg",
  "./icon-192.png", "./icon-512.png", "./apple-touch-icon.png", "./favicon.png", "./badge-96.png"];
self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).catch(() => {}));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  // apaga só versões antigas do próprio AgroN; caches de outros projetos da origem ficam intactos
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith(PREFIX) && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
self.addEventListener("fetch", e => {
  const req = e.request;
  // nunca intercepta/guarda requisições de outros domínios nem de outros caminhos da mesma origem
  if (req.method !== "GET" || !inScope(req.url)) return;
  e.respondWith(
    fetch(req, {cache: "no-store"}).then(res => {
      if (res && res.ok) { const copy = res.clone(); caches.open(CACHE).then(c => c.put(req, copy)); }
      return res;
    }).catch(() => caches.open(CACHE).then(c => c.match(req).then(r => r || (req.mode === "navigate" ? c.match("./index.html") : undefined)))
      .then(r => r || new Response("Sem conexão", {status: 503, headers: {"Content-Type": "text/plain; charset=utf-8"}})))
  );
});
// v22: alerta enviado pelo computador do Informativo (alerts.py). Conteúdo: {title, body, url, tag}.
self.addEventListener("push", e => {
  let m = {};
  try { m = e.data ? e.data.json() : {}; } catch (_) { m = {body: e.data ? e.data.text() : ""}; }
  // só abre páginas do próprio AgroN (mesmo escopo); qualquer outro endereço vira a página inicial
  const safe = inScope(m.url || "./") ? new URL(m.url || "./", SCOPE).href : SCOPE;
  e.waitUntil(self.registration.showNotification(m.title || "AgroN", {
    body: m.body || "", icon: "icon-192.png", badge: "badge-96.png", tag: m.tag || "agron",
    renotify: true, data: {url: safe}, lang: "pt-BR"
  }));
});
// toque na notificação: abre (ou traz para frente) uma aba do AgroN já na cotação certa (?p=...#chave)
self.addEventListener("notificationclick", e => {
  e.notification.close();
  const d = (e.notification.data && e.notification.data.url) || "./";
  const target = inScope(d) ? new URL(d, SCOPE).href : SCOPE;
  e.waitUntil(self.clients.matchAll({type: "window", includeUncontrolled: true}).then(cs => {
    for (const c of cs) {
      if (c.url.startsWith(SCOPE) && "navigate" in c) {
        return c.navigate(target).then(w => (w || c).focus()).catch(() => self.clients.openWindow(target));
      }
    }
    return self.clients.openWindow(target);
  }));
});
