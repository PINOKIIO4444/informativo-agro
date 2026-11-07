"""Resolução dinâmica dos índices oficiais por ano/mês (funções puras sobre HTML; testáveis com fixtures)."""
import re, urllib.parse, html as H
MESES = ['janeiro', 'fevereiro', 'marco', 'abril', 'maio', 'junho', 'julho', 'agosto', 'setembro', 'outubro', 'novembro', 'dezembro']
def _norm(s): return H.unescape(re.sub('<[^>]+>', '', s)).strip().lower().replace('ç', 'c')
def _links(page, base):
    return [(urllib.parse.urljoin(base, h), _norm(t)) for h, t in re.findall(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', page, re.S)]
RJ_BASE = 'https://www.rj.gov.br'
RJ_ROOT = 'https://www.rj.gov.br/ceasa/node/295'
def rj_year_url(root_html, y):
    x = [u for u, t in _links(root_html, RJ_BASE) if t == str(y) and '/ceasa/node/' in u]
    return x[0] if x else None
def rj_month_url(year_html, m):
    x = [u for u, t in _links(year_html, RJ_BASE) if t == MESES[m - 1] and '/ceasa/node/' in u]
    return x[0] if x else None
def rj_pdfs(month_html):
    """{'AAAA-MM-DD': url} a partir do nome do arquivo (dd mm aaaa no nome; grafia/espaços variam)."""
    out = {}
    for h in re.findall(r'href="([^"]+\.pdf)"', month_html):
        n = urllib.parse.unquote(h)
        m = re.search(r'(\d\d)\s+(\d\d)\s+(\d{4})(?:_\d+)?\.pdf$', n)
        if m: out.setdefault(f'{m.group(3)}-{m.group(2)}-{m.group(1)}', urllib.parse.urljoin(RJ_BASE, h))
    return out
SC_BASE = 'https://www.ceasa.sc.gov.br'
SC_ROOT = 'https://www.ceasa.sc.gov.br/index.php/cotacao-de-precos'
def sc_year_url(root_html, y):
    x = sorted({urllib.parse.urljoin(SC_BASE, h) for h in re.findall(r'href="(/index\.php/cotacao-de-precos/%s(?:-\d+)?)"' % y, root_html)})
    return x[0] if x else None
def sc_month_url(year_html, m):
    x = sorted({urllib.parse.urljoin(SC_BASE, h) for h in re.findall(r'href="(/index\.php/cotacao-de-precos/[^"/]+/%02d-%s(?:-\d+)?)"' % (m, MESES[m - 1]), year_html)})
    return x[0] if x else None
def sc_pdfs(month_html):
    out = {}
    for h in re.findall(r'href="([^"]*/\d+-(\d\d)-(\d\d)-(\d{4})/file)"', month_html):
        out.setdefault(f'{h[3]}-{h[2]}-{h[1]}', urllib.parse.urljoin(SC_BASE, h[0]))
    return out
PR_BASE = 'https://www.ceasa.pr.gov.br'
def pr_year_url(y): return f'{PR_BASE}/Pagina/Cotacao-Diaria-de-Precos-{y}'
UNIDADES_PR = ('Curitiba', 'Londrina', 'Maringá', 'Cascavel', 'Foz do Iguaçu')
def pr_pdfs(year_html, y, m):
    """Links do mês (documento/AAAA-MM/...) com o dia pelo texto 'Dia DD' do link. A unidade é conferida depois no cabeçalho do PDF."""
    out = []
    for h, t in re.findall(r'<a[^>]*href="([^"]*/documento/%d-%02d/[^"]+\.pdf)"[^>]*>(.*?)</a>' % (y, m), year_html, re.S):
        dm = re.search(r'Dia\s*(\d{1,2})', _norm(t), re.I)
        if dm: out.append((f'{y}-{m:02d}-{int(dm.group(1)):02d}', urllib.parse.urljoin(PR_BASE, h)))
    return sorted(set(out))
def rs_month_folder(page_html, y, m):
    """Pasta do Drive do mês: o link tem o nome do mês; o ano é o título (>AAAA<) do bloco que vem antes do link."""
    anos = [(k.start(), k.group(1)) for k in re.finditer(r'>\s*(20\d\d)\s*<', page_html)]
    for k in re.finditer(r'<a[^>]*href="(https://drive\.google\.com/drive/folders/[\w-]+)[^"]*"[^>]*>(.*?)</a>', page_html, re.S):
        ano = [a for p, a in anos if p < k.start()]
        if ano and ano[-1] == str(y) and _norm(k.group(2)) == MESES[m - 1]: return k.group(1)
    return None
def rs_files(folder_html):
    return {f'{y}-{mo}-{d}': f'https://drive.google.com/uc?export=download&id={i}'
            for i, d, mo, y in re.findall(r'file/d/([\w-]+)/.*?flip-entry-title">[^<]*?(\d\d)/(\d\d)/(\d{4})', folder_html, re.S)}
def go_pdf(y, m, d): return f'https://goias.gov.br/ceasa/wp-content/uploads/sites/48/{y}/{m:02d}/{d:02d}-{m:02d}-{y}.pdf'
def pe_url(g, y, m, d): return f'https://www.ceasape.org.br/cotacao/{g}?data={d:02d}/{m:02d}/{y}'
