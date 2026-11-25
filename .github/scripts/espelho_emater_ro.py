#!/usr/bin/env python3
"""Espelho da Pesquisa Semanal de Preços da Emater-RO (AgroN).

Roda numa GitHub Action. Baixa, sem alterar, a listagem
http://www.emater.ro.gov.br/ematerro/pesquisa-de-preco/ e os PDFs mais recentes ligados a ela,
e grava em DEST (checkout do branch espelho-emater-ro):
  lista.html                       bytes exatos da listagem
  pdf/AAAA/MM/<arquivo>.pdf        bytes exatos de cada PDF
  manifest.json                    URL original, sha256, tamanho e data/hora (UTC) de cada cópia
Motivo: a máquina que gera o AgroN não consegue abrir HTTP puro e a Emater-RO não tem HTTPS válido.
Nada é calculado aqui; o coletor do AgroN confere o sha256 e lê o PDF como se viesse da Emater.
Fail-closed: se a listagem não vier 200 com o título esperado, nada é sobrescrito.
Só stdlib."""
import datetime as dt, hashlib, html.parser, json, os, re, sys, time, urllib.parse, urllib.request

LISTA = 'http://www.emater.ro.gov.br/ematerro/pesquisa-de-preco/'
HOSTS = {'emater.ro.gov.br', 'www.emater.ro.gov.br'}   # auditfix 25/11: host exato (antes: qualquer nome terminado em emater.ro.gov.br)
UA = 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0 Safari/537.36 AgroN-espelho (+https://agronbr.com.br/)'
MANTER = 6          # PDFs mais novos mantidos no espelho
MAX_PDF = 15 << 20  # 15 MB
RECONFERIR = 3      # auditfix 25/11: os N PDFs mais novos são baixados de novo a cada rodada (revisão na mesma URL)


def get(url, tries=3):
    err = None
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers={'User-Agent': UA}), timeout=60)
            return r.status, r.read(MAX_PDF + 1)
        except Exception as e:
            err = e
            time.sleep(10 * (i + 1))
    raise err


class Links(html.parser.HTMLParser):
    def __init__(self):
        super().__init__()
        self.out, self._href, self._txt = [], None, []

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self._href, self._txt = dict(attrs).get('href'), []

    def handle_data(self, d):
        if self._href is not None:
            self._txt.append(d)

    def handle_endtag(self, tag):
        if tag == 'a' and self._href is not None:
            self.out.append((self._href.strip(), ' '.join(''.join(self._txt).split())))
            self._href = None


def pdfs_da_lista(html_text):
    p = Links()
    p.feed(html_text)
    found = {}
    for href, txt in p.out:
        u = urllib.parse.urljoin(LISTA, href)
        pu = urllib.parse.urlparse(u)
        if pu.scheme not in ('http', 'https') or pu.netloc.lower() not in HOSTS or not pu.path.lower().endswith('.pdf'):
            continue
        m = re.search(r'semana\s*[–—-]\s*(\d{2})/(\d{2})/(\d{4})', txt, re.I)
        if not m:
            continue
        d = dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
        found.setdefault(u, d)
    return sorted(found.items(), key=lambda x: x[1], reverse=True)


def caminho(u):
    pu = urllib.parse.urlparse(u)
    m = re.search(r'/uploads/(\d{4})/(\d{2})/([^/]+\.pdf)$', pu.path, re.I)
    if not m:
        raise ValueError(f'URL de PDF fora do padrão: {u}')
    nome = re.sub(r'[^A-Za-z0-9._-]', '_', urllib.parse.unquote(m.group(3)))
    return f'pdf/{m.group(1)}/{m.group(2)}/{nome}'


def main(dest):
    agora = dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()
    mpath = os.path.join(dest, 'manifest.json')
    man = json.load(open(mpath, encoding='utf-8')) if os.path.exists(mpath) else {}
    man.setdefault('arquivos', {})
    st, raw = get(LISTA)
    txt = raw.decode('utf-8', 'replace')
    if st != 200 or 'Pesquisa Semanal de Pre' not in txt:
        print(f'listagem inválida (HTTP {st}); espelho mantido', file=sys.stderr)
        return 1
    lista = pdfs_da_lista(txt)
    if not lista:
        print('listagem sem PDF datado; espelho mantido', file=sys.stderr)
        return 1
    with open(os.path.join(dest, 'lista.html'), 'wb') as f:
        f.write(raw)
    man['fonte'] = 'Emater-RO — Pesquisa Semanal de Preços (cópia sem alteração)'
    man['lista'] = dict(url=LISTA, path='lista.html', sha256=hashlib.sha256(raw).hexdigest(),
                        bytes=len(raw), obtido_em=agora, http=st)
    novos = [u for u, _ in lista[:MANTER]]
    for i, u in enumerate(novos):
        ent = man['arquivos'].get(u)
        tem = bool(ent and os.path.exists(os.path.join(dest, ent['path'])))
        if tem and i >= RECONFERIR:
            continue  # boletim antigo: não rebaixa
        try:
            st, b = get(u)
        except Exception as e:
            print(f'PDF não baixado {u}: {e}' + (' (mantida a cópia anterior)' if tem else ''), file=sys.stderr)
            continue
        if st != 200 or not b.startswith(b'%PDF') or len(b) > MAX_PDF:
            print(f'PDF recusado {u} (HTTP {st}, {len(b)} bytes)' + (' (mantida a cópia anterior)' if tem else ''), file=sys.stderr)
            continue
        sha = hashlib.sha256(b).hexdigest()
        if tem and sha == ent.get('sha256'):
            ent['conferido_em'] = agora   # mesma versão: só registra a conferência
            continue
        p = caminho(u)
        os.makedirs(os.path.dirname(os.path.join(dest, p)), exist_ok=True)
        tmp = os.path.join(dest, p) + '.tmp'
        with open(tmp, 'wb') as f:
            f.write(b)
        os.replace(tmp, os.path.join(dest, p))
        novo = dict(path=p, sha256=sha, bytes=len(b), obtido_em=agora, http=st)
        if tem:   # a Emater trocou o PDF na mesma URL: guarda o rastro da versão anterior
            novo['revisoes'] = (ent.get('revisoes') or []) + [dict(sha256=ent.get('sha256'), obtido_em=ent.get('obtido_em'))]
            print(f'revisado {p} ({len(b)} bytes; sha256 anterior {str(ent.get("sha256"))[:12]})')
        else:
            print(f'copiado {p} ({len(b)} bytes)')
        man['arquivos'][u] = novo
    for u in [u for u in man['arquivos'] if u not in novos]:  # poda: só os MANTER mais novos
        p = os.path.join(dest, man['arquivos'].pop(u)['path'])
        if os.path.exists(p):
            os.remove(p)
    with open(mpath, 'w', encoding='utf-8') as f:
        json.dump(man, f, ensure_ascii=False, indent=1, sort_keys=True)
        f.write('\n')
    return 0


if __name__ == '__main__':
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else '.'))
