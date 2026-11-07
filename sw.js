// Service worker do AgroN (v27): rede primeiro para a página e os JSON (cotações e notícias frescas).
// O cache só segura a cópia offline. Imagem, ícone e manifesto ficam no cache depois da primeira vez.
// v27: a instalação não baixa index.html de novo (a visita já trouxe a página; antes pedia "./" e "./index.html").
// O histórico do gráfico (hist/*.json) não entra no pré-cache — só é pedido ao abrir uma cotação.
// A rotina do computador (~19:30 America/Sao_Paulo) regrava index.html. Para a primeira página
// continuar leve, essa rotina não deve embutir a série do gráfico: hist/<chave>.json já cobre o detalhe.
// Uma única cópia do HTML fica guardada, mesmo com ?p= na barra de endereço.
// v26: isolado de outros projetos na mesma origem (pinokiio4444.github.io): só mexe nos próprios caches
// ("informativo-agro-*"), só atende requisições dentro do próprio escopo e só foca/abre abas do próprio escopo.
const PREFIX = "informativo-agro-";
const CACHE = PREFIX + "v27";
const SCOPE = self.registration.scope;              // ex.: https://agronbr.com.br/
const inScope = u => { try { return new URL(u, SCOPE).href.startsWith(SCOPE); } catch (_) { return false; } };
// só o que o alerta precisa para aparecer sem rede; o HTML é guardado na navegação, não na instalação
const CORE = ["./icon-192.png", "./badge-96.png"];
const SHELL = new URL("./index.html", SCOPE).href;
const isStatic = u => /\.(png|jpe?g|svg|ico|webp|webmanifest)$/i.test(u.pathname);

self.addEventListener("install", e => {
  e.waitUntil(caches.open(CACHE).then(c => c.addAll(CORE)).catch(() => {}));
  self.skipWaiting();
});
self.addEventListener("activate", e => {
  // apaga só versões antigas do próprio AgroN; caches de outros projetos da origem ficam intactos
  e.waitUntil(caches.keys().then(ks => Promise.all(ks.filter(k => k.startsWith(PREFIX) && k !== CACHE).map(k => caches.delete(k))))
    .then(() => self.clients.claim()));
});
function offline() {
  return new Response("Sem conexão", {status: 503, headers: {"Content-Type": "text/plain; charset=utf-8"}});
}
self.addEventListener("fetch", e => {
  const req = e.request;
  // nunca intercepta/guarda requisições de outros domínios nem de outros caminhos da mesma origem
  // HEAD segue direto (o aviso de "sem conexão" depende disso)
  if (req.method !== "GET" || !inScope(req.url)) return;
  const url = new URL(req.url);
  if (isStatic(url)) {
    e.respondWith((async () => {
      const c = await caches.open(CACHE);
      const hit = await c.match(req);
      if (hit) return hit;
      try {
        const res = await fetch(req);
        if (res && res.status === 200) c.put(req, res.clone());
        return res;
      } catch (_) {
        return hit || offline();
      }
    })());
    return;
  }
  // HTML e JSON: rede primeiro. no-cache revalida (ETag → 304 se não mudou); no-store baixava o arquivo inteiro toda vez.
  const key = req.mode === "navigate" ? SHELL : req;
  e.respondWith((async () => {
    const c = await caches.open(CACHE);
    try {
      const res = await fetch(req, {cache: "no-cache"});
      if (res && res.status === 200) c.put(key, res.clone());
      if (res && res.status === 200) return res;
      const hit = await c.match(key) || await c.match(req);
      if (hit) return hit;
      if (req.mode === "navigate") {
        const shell = await c.match(SHELL) || await c.match("./");
        if (shell) return shell;
      }
      return res || offline();
    } catch (_) {
      const hit = await c.match(key) || await c.match(req) || (req.mode === "navigate" ? await c.match(SHELL) || await c.match("./") : null);
      return hit || offline();
    }
  })());
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
