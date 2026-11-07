"""Regras da cotação Ceasa-PE (Recife). Não baixa página e não é chamado pelo site.

O daily.py, no computador do Informativo, é quem deve passar a emitir isso — só depois de um OK.
Este módulo só descreve a conta: peso único, R$ 0,00 e série que não mistura tipo, embalagem nem procedência.
"""
from __future__ import annotations

import re
import unicodedata


def brl(x: str | None):
    """R$ 0,00 e vazio não são preço. Nunca devolve zero."""
    if x is None:
        return None
    m = re.fullmatch(r"R\$\s*([\d.]+,\d{2})", str(x).strip())
    if not m:
        return None
    v = float(m.group(1).replace(".", "").replace(",", "."))
    return v if v > 0 else None


def peso_exato(und: str | None):
    """Kg da embalagem só quando o boletim traz um peso único.

    Faixa (25-28KG, 13A14, 0,8-1KG, 22a23, 25a27), CENTO, UNID. e ESPIGAS ficam None.
    """
    if not und:
        return None
    u = und.upper().replace(" ", "")
    if re.search(r"\d\s*(-|A)\s*\d", u.replace("KG", "")) or re.search(r"\d-\d", u):
        return None
    if u == "KG":
        return 1.0
    m = re.fullmatch(r"(?:CX\.?|SC\.?|SACO|MOLHO)?(\d+(?:,\d+)?)KG", u)
    return float(m.group(1).replace(",", ".")) if m else None


def rs_kg(comum, und: str | None):
    """R$/kg só com preço e peso único. Faixa não vira média."""
    if comum is None:
        return None, None
    kg = peso_exato(und)
    if kg is None:
        return None, None
    valor = round(comum / kg, 4)
    if kg == 1:
        return valor, "nativo R$/kg"
    return valor, f"calculado: comum ÷ {kg:g} kg (peso exato publicado)"


def slug(s: str) -> str:
    t = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", t).strip("-")


def serie(produto, variedade, embalagem, procedencia, praca: str = "recife") -> str:
    return slug(f"{praca}|{produto}|{variedade or ''}|{embalagem or ''}|{procedencia or ''}")


def variacao(atual, anterior):
    """Variação percentual. Sem cotação (None ou zero) fica de fora — não entra como 0%."""
    if atual is None or anterior is None:
        return None
    if atual == 0 or anterior == 0:
        return None
    return round((atual / anterior - 1) * 100, 4)


def unidade(embalagem: str | None, calculo: str | None):
    """Unidade do preço publicado. R$/kg só quando a fonte já é por kg."""
    emb = embalagem or ""
    u = emb.upper().replace(" ", "")
    if calculo and calculo.startswith("nativo"):
        return "R$/kg", "reais por quilo"
    if u == "CENTO":
        return "R$/cento", "reais por cento"
    if u.startswith("UNID"):
        return "R$/unid.", "reais por unidade"
    if "CX" in u:
        return "R$/cx", _extenso(emb, "caixa")
    if "SC" in u or "SACO" in u:
        return "R$/sc", _extenso(emb, "saco")
    return "R$/emb.", f"reais por {emb}" if emb else "reais"


def cotacao(x: str | None):
    """Preço publicado. Zero, vazio, S/C e s/ cotação não são preço."""
    if x is None:
        return None
    t = str(x).strip()
    if not t:
        return None
    if re.fullmatch(r"s\s*/\s*c", t, re.I) or re.fullmatch(r"s\s*/\s*cota[cç][aã]o", t, re.I):
        return None
    if re.fullmatch(r"0+(?:[.,]0+)?", t):
        return None
    return brl(t) if t.upper().startswith("R$") else _numero(t)


def _numero(t: str):
    m = re.fullmatch(r"[\d.]+,\d{2}", t.strip())
    if not m:
        return None
    v = float(t.replace(".", "").replace(",", "."))
    return v if v > 0 else None


def serie_generica(praca, produto, variedade, classificacao, embalagem, procedencia) -> str:
    """Série que não mistura praça, variedade, classificação, embalagem nem procedência."""
    return slug(
        "|".join(
            [
                praca or "",
                produto or "",
                variedade or "",
                classificacao or "",
                embalagem or "",
                procedencia or "",
            ]
        )
    )


def usar_cotacao(fonte: str | None, coluna: str | None = None) -> bool:
    """A coluna do Ceagesp no Notícias Agrícolas sai atrasada e não entra."""
    if (fonte or "") == "noticias_agricolas" and slug(coluna or "") in {"ceagesp", "sp", "sao-paulo"}:
        return False
    return True


def papel_kg(embalagem: str | None, coluna_rs_kg, preco_embalagem):
    """Separa o quilo da fonte do quilo calculado. Zero na coluna de kg não apaga a embalagem.

    Faixa de peso não vira média. O preço da embalagem volta intacto.
    """
    nativo = coluna_rs_kg if isinstance(coluna_rs_kg, (int, float)) and coluna_rs_kg > 0 else None
    if nativo is not None:
        return {"nativo": nativo, "calculado": None, "texto": "nativo R$/kg", "preco": preco_embalagem}
    valor, txt = rs_kg(preco_embalagem, embalagem)
    if valor is None:
        return {"nativo": None, "calculado": None, "texto": None, "preco": preco_embalagem}
    if peso_exato(embalagem) == 1:
        return {"nativo": valor, "calculado": None, "texto": txt, "preco": preco_embalagem}
    return {"nativo": None, "calculado": valor, "texto": txt, "preco": preco_embalagem}


def alerta(serie_nova, preco_novo, serie_base, preco_base, limiar: float = 10):
    """Alerta só na mesma série, com os dois preços. Outra embalagem ou praça não entra."""
    if not serie_nova or serie_nova != serie_base:
        return None
    v = variacao(preco_novo, preco_base)
    if v is None or abs(v) < limiar:
        return None
    return v


def repeticoes(fechamentos):
    """Conta o mesmo preço no fim da série. Não marca a data como atrasada."""
    if not fechamentos:
        return {"n": 0, "atrasado": False, "data": None}
    data, preco = fechamentos[-1]
    if preco is None:
        return {"n": 0, "atrasado": False, "data": data}
    n = 0
    for _d, p in reversed(fechamentos):
        if p != preco:
            break
        n += 1
    return {"n": n, "atrasado": False, "data": data}


def licenca(termo_explicito: str | None):
    """Acesso público não preenche a licença. Sem termo explícito, fica pendente."""
    if termo_explicito and str(termo_explicito).strip():
        return str(termo_explicito).strip()
    return None


def _extenso(emb: str, recipiente: str) -> str:
    has_kg = "KG" in emb.upper().replace(" ", "")
    m = re.search(r"(\d+(?:,\d+)?)\s*(?:-|A|a)\s*(\d+(?:,\d+)?)", emb, re.I)
    if m:
        a, b = m.group(1), m.group(2)
        miolo = f"{a} a {b}" + (" kg" if has_kg else "")
        return f"reais por {recipiente} de {miolo}" if has_kg else f"reais por {recipiente} {miolo}"
    m2 = re.search(r"(\d+(?:,\d+)?)\s*KG", emb, re.I)
    if m2:
        return f"reais por {recipiente} de {m2.group(1)} kg"
    return f"reais por {recipiente}"
