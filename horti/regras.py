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
