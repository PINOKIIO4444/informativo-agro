"""Leitura comum dos testes do repositório (sem rede, sem publicar)."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def pagina():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    data, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    return html, data


def boletins():
    return {p.stem: load(p) for p in (ROOT / "horti" / "boletins").glob("*.json")}


def medias_civis(pontos, data):
    """Semana segunda–domingo e mês civil da data da cotação; só dias com preço."""
    d = dt.date.fromisoformat(data)
    seg = (d - dt.timedelta(d.weekday())).isoformat()
    sem = [v for k, v in pontos if seg <= k <= data]
    mes = [v for k, v in pontos if k[:7] == data[:7] and k <= data]
    media = lambda xs: sum(xs) / len(xs) if xs else None  # noqa: E731
    return dict(wk=media(sem), wkn=len(sem), mo=media(mes), mon=len(mes))
