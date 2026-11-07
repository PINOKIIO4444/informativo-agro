"""Monta a prévia com o pacote já baixado. Não baixa boletim e não liga a coleta.

Uso: python3 horti/integrar_pacote.py /caminho/bundle.json
Só grava os dias que o arquivo traz. Dia sem preço não entra no histórico.
"""
from __future__ import annotations

import json
import re
import unicodedata
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "horti"))
import regras  # noqa: E402

MERCADOS = [
    ("recife", "Recife", "Ceasa-PE", "Recife", "PE"),
    ("campinas", "Campinas", "Notícias Agrícolas", "Campinas", "SP"),
    ("bh", "Belo Horizonte", "Notícias Agrícolas", "Belo Horizonte", "MG"),
    ("cwb", "Curitiba", "Ceasa-PR", "Curitiba", "PR"),
    ("londrina", "Londrina", "Ceasa-PR", "Londrina", "PR"),
    ("maringa", "Maringá", "Ceasa-PR", "Maringá", "PR"),
    ("cascavel", "Cascavel", "Ceasa-PR", "Cascavel", "PR"),
    ("foz", "Foz do Iguaçu", "Ceasa-PR", "Foz do Iguaçu", "PR"),
    ("poa", "Porto Alegre", "Ceasa-RS", "Porto Alegre", "RS"),
    ("rj", "Rio de Janeiro", "Ceasa-RJ", "Rio de Janeiro", "RJ"),
    ("go", "Goiânia", "Ceasa-GO", "Goiânia", "GO"),
    ("sc", "São José", "Ceasa-SC", "São José", "SC"),
    ("df", "Brasília SIMA", "Ceasa-DF", "Brasília", "DF"),
    ("dfat", "Brasília atacado", "Ceasa-DF (atacado)", "Brasília", "DF"),
    ("vitoria", "Vitória", "Ceasa-ES", "Vitória (Grande Vitória)", "ES"),
]
OFICIAL_ES = "https://ceasa.es.gov.br/bancodedados"
# produto, nome, preferências, termos que só caem se houver outra série
SPECS = [
    ("tomate", "Tomate", ["longa vida extra a", "longa vida debora", "longa vida carmem", "longa vida extra", "extra aa", "extra a", "longa vida", " extra"], ["cereja", "sweet", "grape", "italiano", "rasteiro", "gaucho"]),
    ("batata", "Batata", ["asterix", "comum especial", "lisa extra", "extra", "inglesa comum", "agatha primeira", "agatha", "lisa", "branca", "comum"], ["doce", "yacon", "salsa", "baroa", "bolinha", "aipo", "cara", "iacon"]),
    ("cebola", "Cebola", ["nacional", "amarela mineira", "amarela paulista", "pera", "amarela"], ["roxa", "importada"]),
    ("cenoura", "Cenoura", ["extra a", "extra", "comum"], ["baby"]),
    ("alface", "Alface", ["crespa"], ["americana", "lisa", "mimosa"]),
    ("banana", "Banana", ["prata", "nanica", "caturra"], ["terra", "figo", "maca", "maca", "ouro", "marmelo", "marmela"]),
    ("limao", "Limão", ["taiti", "tahiti", "thaiti"], ["siciliano", "galego", "china", "importado"]),
    ("mamao", "Mamão", ["formosa"], ["hawai", "havaiano", "papaya", "papaia", "haway"]),
    ("pimentao", "Pimentão", ["verde", "vermelho"], ["amarelo", "mini", "capeleti", "malagueta"]),
]
SP_KEY = {
    "tomate": "cg_tomate",
    "batata": "cg_batata",
    "cebola": "cg_cebola",
    "cenoura": "cg_cenoura",
    "alface": "cg_alface",
    "banana": "cg_banana_prata",
}
PE_KEY = {
    "tomate": "pe_tomate_extra",
    "batata": "pe_batata_lavada_lisa",
    "cebola": "pe_cebola_pera",
    "cenoura": "pe_cenoura_primeira",
    "alface": "pe_alface_crespa",
    "banana": "pe_banana_prata",
    "limao": "pe_limao_taiti",
    "mamao": "pe_mamao_formosa",
}
FLAG_OK = ("faixa_", "var12m_", "sem_variacao_", "rs_kg_fonte_0")


def norm(s) -> str:
    t = unicodedata.normalize("NFKD", str(s or "")).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", " ", t).strip()


def slug(s) -> str:
    return regras.slug(s)


def pinhao_coerente(r) -> bool:
    """Pinhão da araucária, com embalagem própria. Pitaia ou tâmara no campo variedade é outra fruta."""
    if norm(r.get("produto")) != "pinhao":
        return False
    var = norm(r.get("variedade"))
    return not any(x in var for x in ("pitaia", "tamara", "pinha", "fruta", "conde"))


def hortifruti(r) -> bool:
    if pinhao_coerente(r):
        return True
    marcas = " ".join(str(f) for f in (r.get("flags") or []))
    if "excluivel_nao_hortifruti" in marcas:
        return False
    g = norm(r.get("grupo"))
    if any(k in g for k in ("flor de vaso", "flores de", "orquidea", "forrac", "ovos", "aves e ovos", "cereais", "graos", "granjeiro", "diversos")):
        return False
    prod = norm(r.get("produto"))
    if prod in {"rosa", "orquidea", "crisantemo", "azaleia", "cactus", "anturio", "anturiun", "primula"}:
        return False
    if prod == "ovo" or prod.startswith("ovo ") or prod.startswith("ovos"):
        return False
    if prod.startswith(("carne", "carnes", "frango", "linguica", "peixe", "pescado", "bovino", "suino", "mel ")):
        return False
    if prod == "mel":
        return False
    return True


def ponto_valido(r) -> bool:
    """Comum fora da faixa, ou mínimo maior que o máximo, não entra em histórico nem variação."""
    if r.get("sem_cotacao") or not r.get("comum"):
        return False
    if r.get("min") and r.get("max") and r["min"] > r["max"]:
        return False
    if "faixa_incoerente" in (r.get("flags") or []):
        return False
    return True


def preco_nome(fonte: str) -> str:
    if fonte == "Ceasa-RJ":
        return "modal"
    if fonte == "Ceasa-RS":
        return "mais frequente"
    return "comum"


def flags_publicas(flags) -> list:
    out = []
    for f in flags or []:
        if str(f).startswith(FLAG_OK) or f == "fonte_manual_navegador_sem_rotina":
            out.append(f)
    return out


def enxuga(r) -> dict:
    keep = (
        "fonte", "praca", "uf", "data", "grupo", "produto", "variedade", "classificacao", "cultivo",
        "embalagem", "kg_embalagem", "procedencia", "min", "comum", "max", "situacao", "sem_cotacao",
        "rs_kg_fonte", "rs_kg_calc", "rs_kg_nota", "var_calc_pct", "var_calc_ref", "repeticoes",
        "serie", "url", "arquivo", "linha", "sha256",
    )
    o = {k: r.get(k) for k in keep}
    o["flags"] = flags_publicas(r.get("flags"))
    if r.get("codigo_fonte"):
        o["codigo_fonte"] = r["codigo_fonte"]
    o["preco_nome"] = preco_nome(r["fonte"])
    if r.get("proveniencia_extra"):
        o["proveniencia_extra"] = [
            {k: x.get(k) for k in ("arquivo", "sha256", "url", "linha")} for x in r["proveniencia_extra"]
        ]
    if "faixa_incoerente" in (r.get("flags") or []) or (r.get("min") and r.get("max") and r["min"] > r["max"]):
        o["fora_da_variacao"] = True
    if r.get("fonte") == "Ceasa-ES":
        o["url_publica"] = OFICIAL_ES
        o["filtro"] = r.get("filtro") or r.get("url")
        o["manual"] = True
    if r.get("url_indice"):
        o["url_indice"] = r["url_indice"]
    return o


def pacote_miudo(r) -> int:
    u = norm(r.get("embalagem"))
    kg = r.get("kg_embalagem") or 0
    if not r.get("embalagem"):
        return 1
    if any(k in u for k in ("bandeja", "bdj", "unidade", "duzia")) or (0 < kg < 2):
        return 2
    return 0


def grau_classe(r) -> int:
    b = norm(" ".join(str(r.get(k) or "") for k in ("produto", "variedade", "classificacao")))
    if re.search(r"\bextra( a{1,2})?\b", b) or norm(r.get("classificacao")) == "1":
        return 0
    if "especial" in b or norm(r.get("classificacao")) == "2":
        return 1
    return 2


def escolhe(rows, pid):
    spec = next(s for s in SPECS if s[0] == pid)
    _, _, prefs, evita = spec
    vivos = [r for r in rows if ponto_valido(r)]
    if not vivos:
        return None
    if pid == "pimentao" and any("faixa_em_conferencia" in (r.get("flags") or []) for r in vivos):
        marcados = [r for r in vivos if "faixa_em_conferencia" in (r.get("flags") or [])]
        return sorted(marcados, key=lambda r: (pacote_miudo(r), r["serie"]))[0]
    blob = lambda r: norm(" ".join(str(r.get(k) or "") for k in ("produto", "variedade", "classificacao")))
    livres = [r for r in vivos if not any(e in blob(r) for e in evita)]
    base = livres or vivos

    def chave(r):
        b = blob(r)
        pref = next((i for i, p in enumerate(prefs) if p in b), len(prefs))
        return (pref, pacote_miudo(r), grau_classe(r), r["serie"])

    return sorted(base, key=chave)[0]


def unidade_de(r, nativo, calculado):
    emb = r.get("embalagem") or ""
    u = emb.upper().replace(" ", "")
    if r.get("kg_embalagem") == 1 or "R$/KG" in u or u in {"KG", "KILO"}:
        return "R$/kg", "reais por quilo"
    if u in {"DZ", "DUZIA"} or "/DZ" in u or "DUZIA" in u:
        return "R$/dz", "reais por dúzia"
    if "CX" in u or "CAIXA" in u:
        return "R$/cx", "reais por caixa " + emb
    if "SC" in u or "SACO" in u:
        return "R$/sc", "reais por saco " + emb
    if "UN" in u:
        return "R$/unid.", "reais por unidade"
    if "BDJ" in u or "BANDEJA" in u:
        return "R$/bdj", "reais por bandeja " + emb
    if "PLT" in u or "PREG" in u:
        return "R$/unid.", "reais por embalagem " + emb
    return "R$/emb.", ("reais por " + emb) if emb else "reais"


def quilos(r):
    fonte = r.get("rs_kg_fonte")
    if isinstance(fonte, (int, float)) and fonte > 0:
        return fonte, None
    if r.get("kg_embalagem") == 1 and r.get("comum"):
        return r["comum"], None
    calc = r.get("rs_kg_calc")
    kg = r.get("kg_embalagem")
    if calc and kg and kg != 1:
        return None, round(float(calc), 2)
    return None, None


def media(pontos, fim, dias):
    limite = date.fromisoformat(fim) - timedelta(days=dias - 1)
    sel = [v for d, v in pontos if date.fromisoformat(d) >= limite]
    if not sel:
        return None, 0
    return round(sum(sel) / len(sel), 4), len(sel)


def item_de(mid, nome_praca, r, pontos, pid_forcado=None):
    precos, amostra = cluster_recente([(d, v) for d, v in pontos if v])
    ultima_data, ultima = precos[-1]
    anterior = precos[-2] if len(precos) > 1 else (None, None)
    nativo, calculado = quilos(r)
    unit, unid = unidade_de(r, nativo, calculado)
    rot = " · ".join(x for x in (r.get("variedade"), r.get("classificacao")) if x and x != "-")
    if pid_forcado:
        pid = pid_forcado
        nome = (r.get("produto") or "Série").title()
    else:
        nome = nome_produto(r)
        pid = next(s[0] for s in SPECS if s[1] == nome)
    key = f"hf_{mid}_{pid}"
    wk, wkn = media(precos, ultima_data, 7)
    mo, mon = media(precos, ultima_data, 31)
    iguais = None
    if r.get("repeticoes") is not None and not r.get("sem_cotacao"):
        iguais = int(r["repeticoes"]) + 1
    conferencia = "faixa_em_conferencia" in (r.get("flags") or [])
    return {
        "key": key,
        "name": nome,
        "unit": unit,
        "dec": 2,
        "cat": "horti",
        "src": f"{r['fonte']} — {nome_praca}",
        "sub": " · ".join(x for x in (nome_praca, rot, r.get("embalagem"), r.get("procedencia")) if x),
        "freq": "diária",
        "d": ultima_data,
        "v": ultima,
        "contract": None,
        "pd": anterior[0],
        "pv": anterior[1],
        "pc": None,
        "chg": regras.variacao(ultima, anterior[1]),
        "wk": wk,
        "wkn": wkn,
        "mo": mo,
        "mon": mon,
        "yad": None,
        "yav": None,
        "yac": None,
        "first": precos[0][0],
        "n": len(precos),
        "cr": [r["fonte"], f"{r['fonte']} — {nome_praca}", OFICIAL_ES if r.get("fonte") == "Ceasa-ES" else r.get("url"), None, None],
        "st": False,
        "hf": {
            "praca_id": mid,
            "praca": nome_praca,
            "titulo": nome_praca + (" · " + rot if rot else ""),
            "rotulo": rot,
            "produto": r.get("produto"),
            "variedade": r.get("variedade"),
            "classificacao": r.get("classificacao"),
            "embalagem": r.get("embalagem"),
            "procedencia": r.get("procedencia"),
            "situacao": r.get("situacao"),
            "min": r.get("min"),
            "comum": r.get("comum"),
            "max": r.get("max"),
            "preco_nome": preco_nome(r["fonte"]),
            "sem": False,
            "calc": calculado is not None,
            "rs_kg": calculado,
            "rs_kg_nativo": nativo if unit != "R$/kg" else None,
            "serie": r["serie"],
            "unid": unid,
            "url": OFICIAL_ES if r.get("fonte") == "Ceasa-ES" else r.get("url"),
            "repeticoes": iguais,
            "conferencia": conferencia,
            "dias": len(precos),
            "amostra": [d for d, _v in amostra],
            "coleta_diaria": False,
            "manual": r.get("fonte") == "Ceasa-ES",
            "sha256": r.get("sha256"),
            "arquivo": r.get("arquivo"),
            "linha": r.get("linha"),
        },
    }, key


def nome_produto(r) -> str:
    b = norm(" ".join(str(r.get(k) or "") for k in ("produto", "variedade")))
    for pid, nome, _, _ in SPECS:
        if pid in b or pid in norm(r.get("produto")):
            return nome
    return (r.get("produto") or "").title()


def serie_pontos(rows, serie):
    dias = {}
    for r in rows:
        if r["serie"] != serie or not ponto_valido(r):
            continue
        dias[r["data"]] = r["comum"]
    return sorted(dias.items())


def cluster_recente(pontos):
    """Um vão de mais de 60 dias separa amostra antiga de fechamento. A amostra não entra no gráfico."""
    if not pontos:
        return pontos, []
    grupos = [[pontos[0]]]
    for prev, cur in zip(pontos, pontos[1:]):
        if (date.fromisoformat(cur[0]) - date.fromisoformat(prev[0])).days > 60:
            grupos.append([cur])
        else:
            grupos[-1].append(cur)
    antigo = [p for g in grupos[:-1] for p in g]
    return grupos[-1], antigo


RAIZ_INDICE = {
    "Ceasa-RJ": "https://www.rj.gov.br/ceasa/node/295",
    "Ceasa-SC": "https://www.ceasa.sc.gov.br/index.php/cotacao-de-precos",
    "Ceasa-RS": "https://ceasa.rs.gov.br/cotacoes-de-precos",
}


def arrumar_url(r, url_inicial):
    """O delta gravou 'ver backfill_log.json' onde o link do dia não veio no pacote."""
    if r.get("url") != "ver backfill_log.json":
        return r
    r = dict(r)
    if url_inicial and str(url_inicial).startswith("http"):
        r["url"] = url_inicial
        return r
    raiz = RAIZ_INDICE.get(r.get("fonte"))
    r["url"] = raiz
    r["url_indice"] = raiz
    return r


def mesclar(inicial, delta, quarentena):
    """O delta substitui o complemento. Chave (série, data). Quarentena sai dos dois lados."""
    bloqueio = {(q["serie"], q["data"]) for q in quarentena}
    urls = {(r["serie"], r["data"]): r.get("url") for r in inicial}
    novo = {}
    for r in delta:
        chave = (r["serie"], r["data"])
        if chave in bloqueio:
            continue
        novo[chave] = arrumar_url(r, urls.get(chave))
    saida = {}
    for r in inicial:
        chave = (r["serie"], r["data"])
        if chave in bloqueio or chave in novo:
            continue
        saida[chave] = r
    saida.update(novo)
    return list(saida.values()), bloqueio


def main(bundle_path: Path, delta_path: Path, quarentena_path: Path):
    inicial = json.loads(bundle_path.read_text(encoding="utf-8"))["registros"]
    delta_doc = json.loads(delta_path.read_text(encoding="utf-8"))
    delta = delta_doc["registros"] if isinstance(delta_doc, dict) else delta_doc
    quarentena = json.loads(quarentena_path.read_text(encoding="utf-8"))
    if len(delta) != 17082:
        raise SystemExit(f"delta com {len(delta)} linhas; o auditado tem 17082")
    brutos, bloqueio = mesclar(inicial, delta, quarentena)
    if any((r["serie"], r["data"]) in bloqueio for r in brutos):
        raise SystemExit("quarentena voltou para a junção")
    keep = [r for r in brutos if hortifruti(r)]
    por = {}
    for mid, nome, fonte, praca, _uf in MERCADOS:
        por[mid] = [r for r in keep if r["fonte"] == fonte and r["praca"] == praca]
    out_dir = ROOT / "horti" / "boletins"
    out_dir.mkdir(exist_ok=True)
    for antigo in (ROOT / "hist").glob("hf_*.json"):
        antigo.unlink()
    itens = []
    head = {pid: [nome, []] for pid, nome, _, _ in SPECS}
    if SP_KEY:
        for pid, key in SP_KEY.items():
            head[pid][1].append(key)
    for pid, key in PE_KEY.items():
        head[pid][1].append(key)
    curadoria = []
    for mid, nome, fonte, praca, uf in MERCADOS:
        rows = por[mid]
        datas = sorted({r["data"] for r in rows})
        ultima = datas[-1]
        pub = [enxuga(r) for r in rows]
        (out_dir / f"{mid}.json").write_text(
            json.dumps(
                {
                    "id": mid,
                    "praca": nome,
                    "fonte": fonte,
                    "uf": uf,
                    "licenca": None,
                    "coleta_diaria": False,
                    "backfill": False,
                    "interpolacao": False,
                    "datas": datas,
                    "ultima": ultima,
                    "linhas": len(pub),
                    "com_preco_na_ultima": sum(1 for r in rows if r["data"] == ultima and not r["sem_cotacao"]),
                    "limites": "Só os dias presentes no pacote. Dia sem preço não entra. Não é série completa.",
                    "registros": pub,
                },
                ensure_ascii=False,
                separators=(",", ":"),
            )
            + "\n",
            encoding="utf-8",
        )
        ultimas = [r for r in rows if r["data"] == ultima]
        for pid, _nome, _, _ in SPECS:
            alvo = [r for r in ultimas if pid in norm(r.get("produto")) or pid in norm(r.get("variedade"))]
            if mid == "recife" and pid in PE_KEY:
                continue
            esc = escolhe(alvo, pid)
            if not esc:
                continue
            pontos = serie_pontos(rows, esc["serie"])
            it, key = item_de(mid, nome, esc, pontos)
            itens.append(it)
            head[pid][1].append(key)
            hist = {"key": key, "first": it["first"], "h": [[d, v] for d, v in pontos if d >= it["first"]], "rolls": []}
            (ROOT / "hist" / f"{key}.json").write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            curadoria.append(
                {
                    "key": key,
                    "id": mid,
                    "produto": pid,
                    "serie": esc["serie"],
                    "data": esc["data"],
                    "comum": esc["comum"],
                    "min": esc["min"],
                    "max": esc["max"],
                    "embalagem": esc.get("embalagem"),
                    "variedade": esc.get("variedade"),
                    "classificacao": esc.get("classificacao"),
                    "repeticoes": it["hf"]["repeticoes"],
                    "st": False,
                    "dias": len(pontos),
                }
            )
    # faixas em conferência que não viraram a série do produto
    ja = {c["serie"] for c in curadoria}
    for mid, nome, fonte, praca, _uf in MERCADOS:
        vistos = set()
        for r in por[mid]:
            if "faixa_em_conferencia" not in (r.get("flags") or []) or r["serie"] in ja or r["serie"] in vistos:
                continue
            if r["data"] != max(x["data"] for x in por[mid] if x["serie"] == r["serie"]):
                continue
            vistos.add(r["serie"])
            pontos = serie_pontos(por[mid], r["serie"])
            if not pontos:
                continue
            it, key = item_de(mid, nome, r, pontos, pid_forcado="rev")
            it["key"] = "hf_" + mid + "_rev_" + slug(r["serie"])[:28]
            it["hf"]["revisao"] = True
            key = it["key"]
            itens.append(it)
            hist = {"key": key, "first": it["first"], "h": [[d, v] for d, v in pontos if d >= it["first"]], "rolls": []}
            (ROOT / "hist" / f"{key}.json").write_text(json.dumps(hist, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8")
            curadoria.append({"key": key, "id": mid, "produto": "revisao", "serie": r["serie"], "data": r["data"], "comum": r["comum"], "max": r["max"], "st": False, "dias": len(pontos)})
    nao = {}
    for nome in ("ceasa_pr", "ceasa_sc", "ceasa_rs"):
        arq = bundle_path.parent / f"{nome}.json"
        bruto = json.loads(arq.read_text(encoding="utf-8"))
        nao[nome] = [
            {"arquivo": a, "linha": b, "texto": c}
            for a, b, c in bruto.get("linhas_nao_lidas") or []
        ]
    (ROOT / "horti" / "nao_lidas.json").write_text(
        json.dumps(
            {
                "nota": "Linhas que o leitor não conseguiu partir. Sem preço inventado.",
                "ceasa_pr": nao["ceasa_pr"],
                "ceasa_sc": nao["ceasa_sc"],
                "ceasa_rs": nao["ceasa_rs"],
            },
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    (ROOT / "horti" / "curadoria.json").write_text(json.dumps(curadoria, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    head_js = [[nome, pid, keys] for pid, (nome, keys) in ((s[0], head[s[0]]) for s in SPECS)]
    rev = [it["key"] for it in itens if it["hf"].get("revisao")]
    patch_index(itens, head_js, rev)
    patch_mercados(por)
    estender_hist_recife(por["recife"])
    (ROOT / "horti" / "quarentena.json").write_text(
        json.dumps(
            [
                {
                    "serie": q["serie"],
                    "data": q["data"],
                    "motivo": q.get("motivo"),
                    "arquivos": [r.get("arquivo") for r in q.get("registros") or []],
                    "sha256": [r.get("sha256") for r in q.get("registros") or []],
                    "precos": [[r.get("min"), r.get("comum"), r.get("max")] for r in q.get("registros") or []],
                }
                for q in quarentena
            ],
            ensure_ascii=False,
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    print(f"itens {len(itens)} revisao {len(rev)} hortifruti {len(keep)}")
    for c in curadoria:
        if c["produto"] != "revisao":
            print(f"{c['id']:10} {c['produto']:8} {c['data']} {c['comum']} {c.get('variedade') or ''} {c.get('classificacao') or ''} dias={c['dias']} rep={c['repeticoes']}")


def patch_mercados(por):
    pracas = [
        {
            "id": "sp",
            "nome": "São Paulo",
            "orgao": "Ceagesp",
            "uf": "SP",
            "cotacoes": "sim",
            "data": None,
            "licenca": None,
            "nota": "Cotações já publicadas no AgroN, pela leitura direta do boletim. A coluna do Ceagesp no Notícias Agrícolas não entra.",
        }
    ]
    for mid, nome, fonte, _praca, uf in MERCADOS:
        datas = sorted({r["data"] for r in por[mid]})
        nota = "Só os dias presentes no pacote. Lacuna não é preenchida. Licença não confirmada. Coleta desligada."
        if mid == "vitoria":
            nota = "Dois dias lidos de PDF no navegador, fonte manual, sem coletor. Página pública: https://ceasa.es.gov.br/bancodedados. Siglas de situação não foram expandidas."
        if mid == "londrina":
            nota = "10 dias úteis no pacote, inclusive 02/11. Em 27/10 há dois PDFs; 127 pares iguais ficaram numa linha com proveniência extra e 129 pares divergentes estão na quarentena, fora do histórico."
        if mid == "cwb":
            nota = "8 dias no pacote. 27/10 não está no arquivo. Sem motivo inventado para a falta."
        if mid == "foz":
            nota = "7 dias. 05/11 e 06/11 não estão no arquivo. A última data publicada é a do boletim."
        pracas.append(
            {
                "id": mid,
                "nome": nome,
                "orgao": fonte,
                "uf": uf,
                "cotacoes": "sim",
                "data": datas[-1],
                "licenca": None,
                "dias": datas,
                "manual": mid == "vitoria",
                "nota": nota,
            }
        )
    doc = {
        "gerado_em": "2026-11-07",
        "coleta_diaria": False,
        "integracao_gerador": False,
        "nota": "Praças com boletim no pacote de 07/11/2026. Acesso público não é licença.",
        "pracas": pracas,
        "conab": {
            "cotacoes": "nenhuma",
            "licenca": "Qualquer parte desta publicação pode ser reproduzida, desde que citada a fonte.",
            "citacao": "CONAB - COMPANHIA NACIONAL DE ABASTECIMENTO. Boletim Hortigranjeiro, Brasília - DF, v. 12, n. 27, outubro, 2026.",
            "url": "https://www.gov.br/conab/pt-br/atuacao/informacoes-agropecuarias/hortigranjeiros-prohort/boletim-hortigranjeiro/2026/boletim-hortigranjeiro_outubro-2026",
            "periodo": "setembro/2026",
            "na_pagina": True,
            "nota": "O boletim de outubro analisa setembro. O resumo semanal 41 é outro documento, de 04/11/2026, sobre outubro frente a setembro, e o texto extraído não traz frase de licença.",
        },
        "hf_brasil": {
            "registros": 0,
            "cotacoes": "nenhuma",
            "licenca": None,
            "autorizacao_series": "pendente",
            "nc": "CC BY-NC 4.0 não autoriza, sozinha, retransmitir a série",
            "url": "https://www.hfbrasil.org.br/",
            "na_pagina": True,
        },
    }
    (ROOT / "horti" / "mercados.json").write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def patch_index(itens, head, rev):
    html_path = ROOT / "index.html"
    html = html_path.read_text(encoding="utf-8")
    i = html.find("const DATA=")
    data, end = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    data["items"] = [it for it in data["items"] if not str(it.get("key", "")).startswith("hf_")]
    # re-encode only by splicing new items before the items array closes
    # Remove previously spliced hf items by rewriting from the parsed object is unsafe
    # (it would reformat every price). Drop old hf_ textually, then insert.
    html = html_path.read_text(encoding="utf-8")
    html = re.sub(r',\{"key":"hf_[^}]*\}(?:\{[^{}]*\})*', "", html)
    # the regex above is too fragile for nested hf objects. Parse spans instead.
    html = html_path.read_text(encoding="utf-8")
    i = html.find("const DATA=")
    data, end = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    spans = []
    dec = json.JSONDecoder()
    pos = html.find("[", i)
    pos += 1
    while True:
        while pos < end and html[pos] in " \n\r\t,":
            pos += 1
        if pos >= end or html[pos] == "]":
            break
        obj, pos2 = dec.raw_decode(html, pos)
        if str(obj.get("key", "")).startswith("hf_"):
            spans.append((pos, pos2))
        pos = pos2
    for a, b in reversed(spans):
        cut_a = a
        if html[cut_a - 1] == ",":
            cut_a -= 1
        html = html[:cut_a] + html[b:]
    blob = ",".join(json.dumps(it, ensure_ascii=False, separators=(",", ":")) for it in itens)
    mark = '],"ref":'
    j = html.find(mark, html.find("const DATA="))
    if j < 0:
        raise SystemExit("fim da lista de cotações não encontrado")
    html = html[:j] + "," + blob + html[j:]
    head_txt = "const HORTI_HEAD=" + json.dumps(head, ensure_ascii=False, separators=(",", ":")) + ";\n"
    rev_txt = "const HORTI_REV=" + json.dumps(rev, ensure_ascii=False, separators=(",", ":")) + ";\n"
    html = re.sub(r"const HORTI_HEAD=.*?;\n", "", html)
    html = re.sub(r"const HORTI_REV=.*?;\n", "", html)
    html = html.replace("const HORTI_VIEW=", head_txt + rev_txt + "const HORTI_VIEW=", 1)
    old_keys = "const HORTI_KEYS=HORTI_VIEW.flatMap(g=>g[1].flatMap(p=>p[1]));"
    new_keys = "const HORTI_KEYS=[...new Set(HORTI_VIEW.flatMap(g=>g[1].flatMap(p=>p[1])).concat(HORTI_HEAD.flatMap(r=>r[2]),HORTI_REV))];"
    if old_keys not in html and new_keys not in html:
        raise SystemExit("HORTI_KEYS ausente")
    html = html.replace(old_keys, new_keys, 1)
    html_path.write_text(html, encoding="utf-8")


def estender_hist_recife(rows):
    """Alonga o gráfico das 33 séries já publicadas com os dias válidos do mesmo produto. Não troca o preço de 06/11."""
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    data, _end = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    for it in data["items"]:
        if not it.get("pe"):
            continue
        p = it["pe"]
        serie = None
        for r in rows:
            if (
                norm(r.get("produto")) == norm(it["name"])
                and norm(r.get("variedade")) == norm(p.get("variedade"))
                and norm(r.get("embalagem")) == norm(p.get("embalagem"))
                and norm(r.get("procedencia")) == norm(p.get("procedencia"))
            ):
                serie = r["serie"]
                break
        if not serie:
            continue
        pontos = serie_pontos(rows, serie)
        recentes, _amostra = cluster_recente(pontos)
        if not recentes:
            continue
        if it["v"] is not None and recentes[-1][1] != it["v"]:
            continue
        hist = {"key": it["key"], "first": recentes[0][0], "h": [[d, v] for d, v in recentes], "rolls": []}
        (ROOT / "hist" / f"{it['key']}.json").write_text(
            json.dumps(hist, ensure_ascii=False, separators=(",", ":")) + "\n", encoding="utf-8"
        )


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit("uso: python3 horti/integrar_pacote.py INICIAL.json DELTA.json QUARENTENA.json")
    main(Path(sys.argv[1]), Path(sys.argv[2]), Path(sys.argv[3]))
