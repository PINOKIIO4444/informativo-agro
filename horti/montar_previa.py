#!/usr/bin/env python3
"""Monta a PRÉVIA de Recife a partir do JSON de staging já conferido.

Não baixa a Ceasa-PE, não chama daily.py, não publica e não é servido pelo site.
Uso: python3 horti/montar_previa.py CAMINHO/recife_staging.json
Grava horti/ceasa-pe.json, hist/pe_*.json e ajusta o index.html desta pasta.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from regras import peso_exato, rs_kg, unidade, variacao

ROOT = Path(__file__).resolve().parents[1]
DIA = "2026-11-06"
ANTE = "2026-11-05"
FONTE = "Ceasa-PE — cotação de hortifrúti no atacado (Recife)"

# key, serie, grupo da página, nome do produto, rótulo da variedade na linha
CURATED = [
    ("pe_tomate_extra", "recife-tomate-extra-cx-25-28kg-pe-pb-ba", "Legumes", "Tomate", "Extra"),
    ("pe_tomate_especial", "recife-tomate-especial-cx-25-28kg-pe-pb-ba", "Legumes", "Tomate", "Especial"),
    ("pe_tomate_primeira", "recife-tomate-primeira-cx-25-28kg-pe-pb-ba", "Legumes", "Tomate", "Primeira"),
    ("pe_tomate_segunda", "recife-tomate-segunda-cx-25-28kg-pe-pb", "Legumes", "Tomate", "Segunda"),
    ("pe_batata_lavada_lisa", "recife-batatinha-lavada-lisa-saco-25-kg-ba-mg", "Legumes", "Batata", "Lavada lisa"),
    ("pe_cebola_pera", "recife-cebola-pera-saco-20-kg-pe-ba", "Legumes", "Cebola", "Pera"),
    ("pe_cebola_roxa", "recife-cebola-roxa-saco-20-kg-pe-ba", "Legumes", "Cebola", "Roxa"),
    ("pe_cenoura_primeira", "recife-cenoura-vermelha-primeira-kg-ba-mg-pe", "Legumes", "Cenoura", "Primeira"),
    ("pe_alface_crespa", "recife-alface-crespa-unid-pe-pb", "Verduras", "Alface", "Crespa"),
    ("pe_repolho_hibrido", "recife-repolho-hibrido-kg-pe", "Verduras", "Repolho", "Híbrido"),
    ("pe_banana_prata", "recife-banana-prata-cat-i-cento-ce", "Frutas", "Banana prata", "Cat. I"),
    ("pe_banana_pacovan", "recife-banana-pacovan-cat-i-kg-kg-pe", "Frutas", "Banana pacovan", "Cat. I"),
    ("pe_laranja_pera", "recife-laranja-pera-kg-se", "Frutas", "Laranja", ""),
    ("pe_mamao_formosa", "recife-mamao-formosa-kg-rn-pe", "Frutas", "Mamão", "Formosa"),
    ("pe_maca_gala", "recife-maca-gala-120a165-frutos-cx-18kg-sc-rs", "Frutas", "Maçã", "120 a 165 frutos"),
    ("pe_uva_italia", "recife-uva-italia-cx-14-18kg-pe", "Frutas", "Uva", "Itália"),
    ("pe_uva_nubia", "recife-uva-nubia-cx-14-18kg-pe", "Frutas", "Uva", "Núbia"),
    ("pe_uva_vitoria", "recife-uva-vitoria-cx-14-18kg-pe", "Frutas", "Uva", "Vitória"),
    ("pe_uva_isabel", "recife-uva-isabel-preta-cx-18-20kg-pe", "Frutas", "Uva", "Isabel preta"),
    ("pe_manga_espada", "recife-manga-espada-cx-23-27kg-pe", "Frutas", "Manga", "Espada"),
    ("pe_manga_rosa", "recife-manga-rosa-cx-23-27kg-pe", "Frutas", "Manga", "Rosa"),
    ("pe_manga_tommy_g", "recife-manga-tommy-grande-cx-23-27kg-pe", "Frutas", "Manga", "Tommy grande"),
    ("pe_manga_tommy_p", "recife-manga-tommy-pequena-cx-23-27kg-pe", "Frutas", "Manga", "Tommy pequena"),
    ("pe_melancia_grande", "recife-melancia-redonda-grande-kg-pe-rn-ba", "Frutas", "Melancia", "Grande"),
    ("pe_melancia_pequena", "recife-melancia-redonda-pequena-kg-pe-rn-ba", "Frutas", "Melancia", "Pequena"),
    ("pe_melancia_sem", "recife-melancia-redonda-sem-semente-kg-pe-rn-ba", "Frutas", "Melancia", "Sem semente"),
    ("pe_melao_espanhol", "recife-melao-espanhol-kg-pe-rn", "Frutas", "Melão", "Espanhol"),
    ("pe_melao_japones", "recife-melao-japones-kg-rn", "Frutas", "Melão", "Japonês"),
    ("pe_tangerina_cravo", "recife-tangerina-cravo-cx-25kg-pe", "Frutas", "Tangerina", "Cravo"),
    ("pe_tangerina_verona", "recife-tangerina-verona-cx-25kg-ba", "Frutas", "Tangerina", "Verona"),
    ("pe_tangerina_ponkan", "recife-tangerina-ponkan-cx-22a23kg-pb", "Frutas", "Tangerina", "Ponkan"),
    ("pe_tangerina_murcott", "recife-tangerina-murcott-cx-25kg-sp", "Frutas", "Tangerina", "Murcott"),
    ("pe_limao_taiti", "recife-limao-taiti-cx-25a27-sp-ba-pe", "Frutas", "Limão", ""),
]
ORDER = [
    ("Legumes", ["Tomate", "Batata", "Cebola", "Cenoura"]),
    ("Verduras", ["Alface", "Repolho"]),
    ("Frutas", ["Banana nanica", "Banana prata", "Banana pacovan", "Laranja", "Mamão", "Maçã", "Uva", "Manga", "Melancia", "Melão", "Tangerina", "Limão"]),
]
CG = {
    "Tomate": ["cg_tomate"],
    "Batata": ["cg_batata"],
    "Cebola": ["cg_cebola"],
    "Cenoura": ["cg_cenoura"],
    "Alface": ["cg_alface"],
    "Repolho": ["cg_repolho"],
    "Banana nanica": ["cg_banana_nanica"],
    "Banana prata": ["cg_banana_prata"],
    "Laranja": ["cg_laranja"],
    "Mamão": ["cg_mamao"],
    "Maçã": ["cg_maca"],
}
KEEP = [
    "praca", "fonte", "grupo", "data", "produto", "variedade", "embalagem", "procedencia",
    "min", "comum", "max", "situacao", "sem_cotacao", "texto_original", "kg_embalagem",
    "rs_kg_comum", "rs_kg_calculo", "serie", "url",
]


def _by_serie(regs):
    out = {}
    for r in regs:
        out.setdefault(r["serie"], {})[r["data"]] = r
    return out


def _item(key, produto, rotulo, hoje, ontem):
    comum = None if hoje["sem_cotacao"] else hoje["comum"]
    prev = None
    if ontem and not ontem["sem_cotacao"] and ontem["comum"] is not None:
        prev = ontem["comum"]
    calc_txt = hoje["rs_kg_calculo"] or ""
    calculado = bool(calc_txt.startswith("calculado")) and comum is not None
    unit, unid = unidade(hoje["embalagem"], hoje["rs_kg_calculo"] if comum is not None else None)
    pts = []
    for dia, rec in ((ANTE, ontem), (DIA, hoje)):
        if rec and not rec["sem_cotacao"] and rec["comum"] is not None:
            pts.append([dia, rec["comum"]])
    vals = [p[1] for p in pts]
    media = round(sum(vals) / len(vals), 4) if vals else None
    sub = "Recife"
    if rotulo:
        sub += " · " + rotulo
    sub += " · " + (hoje["embalagem"] or "")
    if hoje.get("procedencia"):
        sub += " · " + hoje["procedencia"]
    return {
        "key": key,
        "name": produto,
        "unit": unit,
        "dec": 2,
        "cat": "horti",
        "src": "Ceasa-PE — cotação de atacado em Recife (prévia de 06/11/2026)",
        "sub": sub,
        "freq": "diária",
        "d": DIA,
        "v": comum,
        "contract": None,
        "pd": ANTE if prev is not None else None,
        "pv": prev,
        "pc": None,
        "chg": variacao(comum, prev),
        "wk": media,
        "wkn": len(vals),
        "mo": media,
        "mon": len(vals),
        "yad": None,
        "yav": None,
        "yac": None,
        "first": pts[0][0] if pts else None,
        "n": len(pts),
        "cr": ["Ceasa-PE", FONTE, hoje["url"], None, None],
        "st": False,
        "pe": {
            "praca": "Recife (Ceasa-PE)",
            "rotulo": rotulo,
            "variedade": hoje["variedade"],
            "embalagem": hoje["embalagem"],
            "procedencia": hoje["procedencia"],
            "situacao": hoje["situacao"],
            "min": hoje["min"],
            "comum": hoje["comum"],
            "max": hoje["max"],
            "sem": bool(hoje["sem_cotacao"] or comum is None),
            "calc": calculado,
            "rs_kg": hoje["rs_kg_comum"] if calculado else None,
            "serie": hoje["serie"],
            "unid": unid,
            "url": hoje["url"],
            "previa": True,
            "coleta_diaria": False,
        },
    }, {"key": key, "first": pts[0][0] if pts else None, "h": pts, "rolls": []}


def _view(items_by_prod):
    view = []
    for grupo, nomes in ORDER:
        bloco = []
        for nome in nomes:
            keys = list(CG.get(nome, [])) + items_by_prod.get(nome, [])
            bloco.append([nome, keys])
        view.append([grupo, bloco])
    return view


def _slim(r):
    o = {k: r[k] for k in KEEP}
    # confere a conta de novo; o arquivo de prévia não carrega um kg inventado
    kg = peso_exato(r["embalagem"])
    valor, txt = rs_kg(None if r["sem_cotacao"] else r["comum"], r["embalagem"])
    if kg != r["kg_embalagem"] or valor != r["rs_kg_comum"] or (txt or None) != (r["rs_kg_calculo"] or None):
        raise SystemExit(f"conta divergente em {r['serie']} {r['data']}: {kg} {valor} {txt}")
    if r["sem_cotacao"] and (r["comum"] not in (None, 0) or r["comum"] == 0):
        raise SystemExit(f"sem cotação com preço em {r['serie']}")
    if r["comum"] == 0:
        raise SystemExit(f"preço zero em {r['serie']}")
    return o


def boletim(staging: dict) -> dict:
    regs = staging["registros"]
    slim = [_slim(r) for r in regs]
    cont = {}
    for dia in (ANTE, DIA):
        rows = [r for r in slim if r["data"] == dia]
        cont[dia] = {"linhas": len(rows), "com_preco": sum(1 for r in rows if not r["sem_cotacao"] and r["comum"] is not None)}
    if cont[DIA] != {"linhas": 164, "com_preco": 140}:
        raise SystemExit(f"contagem 06/11 inesperada: {cont[DIA]}")
    return {
        "praca": "Recife (Ceasa-PE)",
        "fonte": "Ceasa-PE",
        "previa": True,
        "coleta_diaria": False,
        "licenca": "pendente",
        "gerado_em": staging.get("gerado_em"),
        "boletim": DIA,
        "anterior": ANTE,
        "contagem": cont,
        "nota": "Prévia com os boletins de 05/11 e 06/11/2026. Não é coleta diária. Licença de republicação pendente.",
        "registros": slim,
    }


def serie_items(regs):
    by = _by_serie(regs)
    items, hists, por_prod = [], [], {}
    vistos = set()
    for key, serie, grupo, produto, rotulo in CURATED:
        if serie in vistos:
            raise SystemExit("série repetida na curadoria: " + serie)
        vistos.add(serie)
        dias = by.get(serie)
        if not dias or DIA not in dias:
            raise SystemExit("série ausente no staging: " + serie)
        item, hist = _item(key, produto, rotulo, dias[DIA], dias.get(ANTE))
        if item["pe"]["sem"]:
            if item["v"] is not None or item["chg"] is not None or hist["h"]:
                raise SystemExit("sem cotação entrou na variação: " + key)
        if peso_exato(item["pe"]["embalagem"]) is None and (item["pe"]["calc"] or item["pe"]["rs_kg"] is not None):
            raise SystemExit("faixa virou kg: " + key)
        items.append(item)
        hists.append(hist)
        por_prod.setdefault(produto, []).append(key)
        if grupo not in {g for g, _ in ORDER}:
            raise SystemExit(grupo)
    return items, hists, _view(por_prod)


def patch_data(html: str, items, src_url: str) -> str:
    marker = "const DATA="
    i = html.find(marker)
    if i < 0:
        raise SystemExit("DATA ausente")
    data, end = json.JSONDecoder().raw_decode(html, i + len(marker))
    kept = []
    for it in data["items"]:
        if not isinstance(it, dict):
            kept.append(it)
            continue
        if it.get("pe") or str(it.get("key", "")).startswith("pe_"):
            continue
        it.pop("h", None)
        it.pop("rolls", None)
        kept.append(it)
    cg = next(x for x in kept if x["key"] == "cg_tomate")
    if cg["v"] != 14.44 or cg["d"] != DIA:
        raise SystemExit("preço do tomate Ceagesp mudou; abortando")
    data["items"] = kept + items
    srcs = [c for c in data.get("srcs") or [] if not (isinstance(c, list) and c and c[0] == "Ceasa-PE")]
    srcs.append(["Ceasa-PE", FONTE, src_url, None, None])
    data["srcs"] = srcs
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    note = "// v55: a série do gráfico não entra nesta página — a primeira tela não desenha histórico. O detalhe busca hist/<chave>.json.\n"
    prefix = html[:i]
    if "v55: a série do gráfico não entra" not in prefix[-400:]:
        prefix += note
    return prefix + marker + blob + html[end:]


def _swap(new: str, old: str, start: str, end: str) -> str:
    ni, oi = new.find(start), old.find(start)
    if ni < 0 or oi < 0 or new.find(start, ni + 1) != -1 or old.find(start, oi + 1) != -1:
        raise SystemExit("marcador não único: " + start[:48])
    nj, oj = new.find(end, ni), old.find(end, oi)
    if nj < 0 or oj < 0:
        raise SystemExit("fim ausente: " + end[:48])
    return new[:ni] + old[oi:oj] + new[nj:]


def restore_pr3(html: str) -> str:
    old = subprocess.check_output(["git", "show", "0647819:index.html"], cwd=ROOT, text=True)
    html = _swap(html, old, "function spark(h,n=30){", "\nconst REF=DATA.ref;")
    html = _swap(html, old, "/*v38: tabela da Scot por praça atrasada.", "/*v43: pesquisas estaduais")
    html = _swap(html, old, "const H0=HIST[dk]", "const last=hd.length")
    html = html.replace(
        "/*v19: index.html traz só os últimos registros; período que eles não cobrem espera o hist/ (ou, sem conexão, mostra o que tem)*/",
        "/*v55: a primeira página não traz a série do gráfico. Qualquer período espera hist/<chave>.json; sem conexão, mostra o que já estiver guardado*/",
        1,
    )
    html = html.replace(
        "média simples dos valores do dia das ${G.n} fontes oficiais${ufs48(G)",
        "média simples dos valores publicados pelas ${G.n} fontes oficiais (data do indicador ou do dia útil anterior)${ufs48(G)",
        1,
    )
    html = html.replace(
        "média simples dos valores do dia das ${G.n} fontes oficiais que entram no cálculo${ufs48(G)",
        "média simples dos valores publicados pelas ${G.n} fontes oficiais que entram no cálculo (data do indicador ou do dia útil anterior)${ufs48(G)",
        1,
    )
    html = _swap(html, old, "const FOC='a[href],button:not([disabled])", "// Tab preso na camada aberta")
    html = _swap(html, old, "function fbOpenForm(){", "fbBind();\n")
    # o bloco antigo começa em fbFormNote, antes de fbOpenForm
    if "function fbFormNote()" not in html:
        oi = old.find("function fbFormNote()")
        oj = old.find("fbBind();\n", oi)
        ni = html.find("function fbOpenForm(){")
        nj = html.find("fbBind();\n", ni)
        if min(oi, oj, ni, nj) < 0:
            raise SystemExit("fbSend não alinhou")
        html = html[:ni] + old[oi:oj] + html[nj:]
    # Esc da pilha: tira os atalhos soltos e devolve o listener único
    html = html.replace(
        '  document.addEventListener("keydown",e=>{if(e.key==="Escape")fbClose()});\n',
        "",
        1,
    )
    html = html.replace(
        '  document.addEventListener("keydown",e=>{if(e.key==="Escape"&&document.getElementById("pmc")?.classList.contains("on"))pmClose()});\n',
        "",
        1,
    )
    if 'if(e.key!=="Escape")return;\n  const pm=document.getElementById("pmc")' not in html:
        tail = old[old.find('document.addEventListener("keydown",e=>{\n  if(e.key!=="Escape")return;\n  const pm=document.getElementById("pmc")'):]
        if "const pm=document.getElementById" not in tail:
            raise SystemExit("listener de Esc ausente no 0647819")
        # o tail inclui o fechamento do script; cola antes de </script> final
        k = html.rfind("</script>")
        html = html[:k] + "\n" + tail[tail.find("document.addEventListener"):tail.rfind("</script>")] + html[k:]
    if "res.ok" not in html or "ck>=e" in html:
        raise SystemExit("PR3 JS não voltou (feedback ou atalho da Scot)")
    if "Array.isArray(x)?x[1]:x" not in html:
        raise SystemExit("spark sem a guarda de lista")
    return html


UI = r"""
/*HPE prévia Recife (Ceasa-PE): segunda praça do hortifrúti. Não é coleta diária.*/
function hortiLabel(){return DATA.items.some(x=>x&&x.pe)?"Hortifrúti":"Hortifrúti (Ceagesp)"}
function hortiRow(x){
 const pe=x.pe,mkt=pe?"Recife (Ceasa-PE)":"São Paulo (Ceagesp)";
 const rot=pe&&pe.rotulo?pe.rotulo:"";
 const titulo=pe?(rot?"Recife · "+rot:"Recife"):"São Paulo (Ceagesp)";
 const bits=[];
 if(pe){if(pe.embalagem)bits.push(pe.embalagem);if(pe.procedencia)bits.push(pe.procedencia);bits.push(fds(x.d));if(pe.situacao)bits.push(String(pe.situacao).toLowerCase())}
 else{if(x.sub)bits.push(x.sub);bits.push(ud49(x));bits.push(fds(x.d))}
 let faixa="";
 if(pe){if(pe.sem||x.v==null)faixa="sem cotação";else faixa=`mín. ${fmt(pe.min,x.dec)} · comum ${fmt(pe.comum,x.dec)} · máx. ${fmt(pe.max,x.dec)}`+(pe.calc&&pe.rs_kg!=null?` · ${fmt(pe.rs_kg,2)}/kg calculado (peso publicado)`:"")}
 const preco=x.v==null?"sem cotação":mt(x.v,x.dec,x,1);
 const aria=`${titulo}, ${mkt}, ${bits.join(", ")}: ${preco}${x.v==null?"":", "+pctX(x)}. Abrir detalhes`;
 return `<a class="row" href="#${x.key}" onclick="return nav(event,()=>openDet('${x.key}'))" aria-label="${esc(aria)}"><div><div class="n">${esc(titulo)}</div><div class="s">${esc(bits.join(" · "))}${faixa?` · ${esc(faixa)}`:""}</div></div><div class="r"><div class="v">${x.v==null?"—":mv(x.v,x.dec,x,1)}</div>${x.v==null?'<span class="pill z">—</span>':pl(x)}</div></a>`}
function peLinha(x){
 const p=x.pe;if(!p)return "";
 const faixa=p.sem||x.v==null?"Sem cotação neste boletim.":`Mín. ${fmt(p.min,x.dec)} · comum ${fmt(p.comum,x.dec)} · máx. ${fmt(p.max,x.dec)}`;
 const kg=p.calc&&p.rs_kg!=null?`<div style="font-size:13px;color:var(--mu);margin:4px 0">${fmt(p.rs_kg,2)}/kg · calculado (peso publicado)</div>`:"";
 const bits=[p.rotulo,p.embalagem,p.procedencia,p.situacao?String(p.situacao).toLowerCase():""].filter(Boolean);
 return `<div style="font-size:13px;color:var(--mu);margin:4px 0">${esc(faixa)}</div>${kg}<div style="font-size:13px;color:var(--mu);margin:4px 0">${esc(bits.join(" · "))}</div>`}
function peBol(el){
 if(!el.open)return;const b=document.getElementById("pebolb");if(!b||b.dataset.ok)return;
 b.innerHTML='<div class="note">Carregando boletim…</div>';
 fetch("horti/ceasa-pe.json",{cache:"no-cache"}).then(r=>{if(!r.ok)throw new Error("http");return r.json()}).then(j=>{
  const rows=(j.registros||[]).filter(r=>r.data==="2026-11-06");
  const n=rows.length,p=rows.filter(r=>!r.sem_cotacao&&r.comum!=null).length;
  const body=rows.map(r=>{const nome=[r.produto,r.variedade&&r.variedade!=="-"?r.variedade:""].filter(Boolean).join(" · ");
   const meta=[r.embalagem,r.procedencia,r.situacao?String(r.situacao).toLowerCase():""].filter(Boolean).join(" · ");
   const sem=!!(r.sem_cotacao||r.comum==null);const fx=sem?"sem cotação":`mín. ${fmt(r.min,2)} · máx. ${fmt(r.max,2)}`;
   return `<div class="row" style="cursor:default"><div><div class="n">${esc(nome)}</div><div class="s">${esc(meta)} · ${fds(r.data)}</div></div><div class="r"><div class="v">${sem?"—":fmt(r.comum,2)}</div><div class="s">${esc(fx)}</div></div></div>`}).join("");
  b.dataset.ok="1";
  b.innerHTML=`<div class="note">${n} linhas no boletim de 06/11/2026, ${p} com preço. Cada linha é uma série: produto, variedade, embalagem e procedência não se misturam. Sem cotação fica — e não entra na variação.</div><div class="list" style="margin:0;border:0;border-radius:0">${body}</div>`}).catch(()=>{b.innerHTML='<div class="note">Não foi possível abrir o boletim completo.</div>'})}
function hortiPage(it){
 const s=it.sec;
 const chips=`<nav class="chips sib49" id="chips">`+s.items.map(o=>`<a class="chip ${o.id===it.id?"on":""}" href="?p=${o.id}" onclick="return nav(event,()=>go('${o.id}'))" ${o.id===it.id?'aria-current="page"':""} style="text-decoration:none">${o.label}</a>`).join("")+`</nav>`;
 let h=FX49?`<div class="crumb prod49">${chips}<div class="ttl">${ico(it.ic,"tt")}${esc(it.label)}</div></div>`
  :`<div class="crumb"><div class="sec2">${s.label}</div><div class="ttl">${ico(it.ic,"tt")}${esc(it.label)}</div></div>${chips}`;
 if(!FX49)h+=`<div class="note">${NOTES.ceagesp}</div>`;
 const uh=hs("https://www.ceasape.org.br/cotacao/hortalicas?data=06/11/2026"),uf=hs("https://www.ceasape.org.br/cotacao/frutas?data=06/11/2026");
 const la=u=>u?`<a href="${esc(u)}" target="_blank" rel="noopener">`:"";
 h+=`<div class="note">Prévia da <b>Ceasa-PE</b>, boletim de 06/11/2026 (${la(uh)}hortaliças ↗</a> · ${la(uf)}frutas ↗</a>): 164 linhas, 140 com preço. A coleta diária não está ligada. Cada linha da lista é uma série — variedade, embalagem e procedência separadas. Onde a fonte não tem preço, aparece — e a linha fica fora da variação. Tomate (caixa 25–28 kg) e uva (caixa 14–18 kg) continuam em reais por caixa. R$/kg calculado só quando a embalagem traz um peso único, com o rótulo. Licença de republicação pendente: as páginas públicas não trazem termo de uso nem proibição, e isso não autoriza publicar.</div>`;
 h+=`<div class="list${FX49?" main49":""}">`;
 HORTI_VIEW.forEach(([grp,prods])=>{h+=`<div class="sec">${esc(grp)}</div>`;
  prods.forEach(([nome,ks])=>{const xs=ks.map(k=>I[k]).filter(Boolean);if(!xs.length)return;
   const pracas=new Set(xs.map(x=>x.pe?"Recife":"São Paulo"));
   h+=`<div class="sec">${esc(nome)}${pracas.size>1?" · por praça":""}</div>`;
   xs.forEach(x=>{h+=hortiRow(x)})})});
 h+=`</div><details class="ficha" id="pebol" ontoggle="peBol(this)"><summary>Boletim completo · Ceasa-PE 06/11/2026${ico("seta")}</summary><div id="pebolb"><div class="note">O arquivo traz as 164 linhas do dia, com mínimo, comum, máximo, embalagem, procedência e situação.</div></div></details>`;
 h+=pageSrc(keysOf(it));
 return h}
"""


def apply_ui(html: str, view) -> str:
    # A página já tem a prévia. Rodar de novo não reabre a lista de 164 linhas
    # nem troca a camada das praças pelo script antigo.
    if "/*HPE prévia Recife" in html or "/*HPE prévia:" in html:
        return html
    view_js = "const HORTI_VIEW=" + json.dumps(view, ensure_ascii=False, separators=(",", ":")) + ";\nconst HORTI_KEYS=HORTI_VIEW.flatMap(g=>g[1].flatMap(p=>p[1]));\n"
    needle = "const NAV=["
    i = html.find(needle)
    if i < 0:
        raise SystemExit("NAV ausente")
    html = html[:i] + UI + view_js + html[i:]
    old = '{id:"horti",label:"Hortifrúti (Ceagesp)",ic:"horti",g:[["Legumes",["cg_tomate","cg_batata","cg_cebola","cg_cenoura"]],["Verduras",["cg_alface","cg_repolho"]],["Frutas",["cg_banana_nanica","cg_banana_prata","cg_laranja","cg_mamao","cg_maca"]]],note:"ceagesp",req:"cg_tomate"}]},'
    new = '{id:"horti",label:hortiLabel(),ic:"horti",g:[["",HORTI_KEYS]],note:"ceagesp",req:"cg_tomate",horti:true}]},'
    if old not in html:
        raise SystemExit("entrada horti do menu não encontrada")
    html = html.replace(old, new, 1)
    html = html.replace(
        "function product(it){\n const s=it.sec;if(it.news)return newsPage(it);if(it.ov)return animal40(it);",
        "function product(it){\n const s=it.sec;if(it.news)return newsPage(it);if(it.ov)return animal40(it);if(it.horti)return hortiPage(it);",
        1,
    )
    html = html.replace(
        '"R$/engradado":["R$","/engr.","reais por engradado"]};',
        '"R$/engradado":["R$","/engr.","reais por engradado"],"R$/cx":["R$","/cx","reais por caixa"],"R$/cento":["R$","/cento","reais por cento"],"R$/unid.":["R$","/unid.","reais por unidade"]};',
        1,
    )
    html = html.replace(
        'const cu=x=>{const u=x.key==="usd"?"R$/US$":x.unit;return UNI[u]||["","",u||""]};',
        'const cu=x=>{const u=x.key==="usd"?"R$/US$":x.unit;if(UNI[u])return UNI[u];if(x.pe&&typeof u==="string"&&u.startsWith("R$/"))return ["R$","/"+u.slice(3),(x.pe.unid||u)];return ["","",u||""]};',
        1,
    )
    html = html.replace(
        'horti:"hortifruti horti fruta frutas verdura verduras legume legumes ceagesp"',
        'horti:"hortifruti horti fruta frutas verdura verduras legume legumes ceagesp recife ceasa-pe ceasape uva manga melancia melao tangerina limao"',
        1,
    )
    html = html.replace(
        '  "Ceagesp":"hortifrúti e amendoim no atacado",\n',
        '  "Ceagesp":"hortifrúti e amendoim no atacado",\n  "Ceasa-PE":"hortifrúti em Recife, boletim de 06/11/2026 (prévia, sem coleta diária)",\n',
        1,
    )
    html = html.replace(
        " DATA.items.forEach(x=>{if(x.v==null)return;const st=x.cat===\"estado\",p=st?\"boi\":KP[x.key];if(!p||!NI[p])return;\n",
        " DATA.items.forEach(x=>{if(x.v==null)return;const st=x.cat===\"estado\",p=st?\"boi\":KP[x.key];if(!p||!NI[p])return;\n",
        1,
    )
    anchor = 'add(x.name,subX(x)+" · "+ud(x)+(st?" · Datagro":""),st||cnt[x.name]>1?1:2,p,NI[p].ic,{k:x.key},(SYN40[p]||"")+(st?" estado":""),mt(x.v,x.dec,x))});\n'
    extra = anchor + ' DATA.items.forEach(x=>{if(!x.pe||x.v!=null)return;add(x.name,(subX(x)||"Recife")+" · sem cotação",1,"horti","horti",{k:x.key},SYN40.horti,"—")});\n'
    if anchor not in html:
        raise SystemExit("busca sem âncora")
    html = html.replace(anchor, extra, 1)
    html = html.replace(
        '<div class="big">${mv(x.v,x.dec,x)}</div><div>${pl0(x)}',
        '<div class="big">${mv(x.v,x.dec,x)}</div>${peLinha(x)}<div>${pl0(x)}',
        1,
    )
    html = html.replace(
        'function freqTxt(x){if(/^cg_/.test(x.key))return "boletins de segunda, quarta e sexta";',
        'function freqTxt(x){if(x.pe)return "boletim de prévia (06/11/2026); a coleta diária não está ligada";if(/^cg_/.test(x.key))return "boletins de segunda, quarta e sexta";',
        1,
    )
    old_u = '{const z=cu(x);R("Unidade",`${esc(ud(x))} <span class="mvw">(${esc((cuP(z)+cuS(z)).trim())})</span>`)}'
    new_u = '{const z=cu(x);const lu=x.pe&&x.pe.unid?x.pe.unid:ud(x);R("Unidade",`${esc(lu)} <span class="mvw">(${esc((cuP(z)+cuS(z)).trim())})</span>`)}'
    if old_u not in html:
        raise SystemExit("ficha unidade não encontrada")
    html = html.replace(old_u, new_u, 1)
    old_f = 'else R("Fonte",SL(c)+LIC(c));'
    new_f = '''else R("Fonte",SL(c)+LIC(c));
 if(x.pe){const p=x.pe;if(p.rotulo)R("Variedade",esc(p.rotulo));if(p.embalagem)R("Embalagem",esc(p.embalagem));if(p.procedencia)R("Procedência",esc(p.procedencia));if(p.situacao)R("Situação",esc(String(p.situacao).toLowerCase()));
  R("Mínimo, comum e máximo",(p.sem||x.v==null)?"—":esc(fmt(p.min,x.dec)+" · "+fmt(p.comum,x.dec)+" · "+fmt(p.max,x.dec)));
  if(p.calc&&p.rs_kg!=null)R("R$/kg",esc(fmt(p.rs_kg,2)+" · calculado (peso publicado)"));
  R("Atualização","prévia do boletim de 06/11/2026; a coleta diária não está ligada. Licença de republicação pendente.")}'''
    if old_f not in html:
        raise SystemExit("ficha fonte não encontrada")
    html = html.replace(old_f, new_f, 1)
    return html


def main():
    if len(sys.argv) != 2:
        raise SystemExit("uso: python3 horti/montar_previa.py STAGING.json")
    staging = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    doc = boletim(staging)
    items, hists, view = serie_items(doc["registros"])
    out = ROOT / "horti" / "ceasa-pe.json"
    out.write_text(json.dumps(doc, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    hist = ROOT / "hist"
    for h in hists:
        (hist / f"{h['key']}.json").write_text(json.dumps(h, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
    index = ROOT / "index.html"
    html = index.read_text(encoding="utf-8")
    html = patch_data(html, items, "https://www.ceasape.org.br/cotacao/frutas?data=06/11/2026")
    html = restore_pr3(html)
    html = apply_ui(html, view)
    index.write_text(html, encoding="utf-8")
    print(f"{len(doc['registros'])} registros, {len(items)} séries na lista, {len(hists)} hist")


if __name__ == "__main__":
    main()
