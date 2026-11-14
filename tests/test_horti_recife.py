"""Recife (Ceasa-PE) na página: cartões vêm do boletim publicado, sem inventar preço. Não fala com a rede.
14/11/2026: saíram os testes de horti/regras.py (fora do repositório desde 09/11) e os valores fixos do boletim de
06/11; a coleta diária atualiza Recife, então o teste confere coerência e não um dia específico."""
from __future__ import annotations

import datetime as dt
import json
import re
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def data():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    obj, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    return html, obj


FAIXA = re.compile(r"\d\s*(-|A)\s*\d", re.I)   # "CX 25-28KG", "CX.13A14": faixa de peso, sem R$/kg calculado


class Pagina(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.data = data()
        cls.by = {it["key"]: it for it in cls.data["items"]}
        cls.pe = [it for it in cls.data["items"] if it.get("pe")]

    def test_dados_sem_serie(self):
        self.assertTrue(all("h" not in it and "rolls" not in it for it in self.data["items"]))

    def test_lista_curada_nao_mistura(self):
        self.assertEqual(len(self.pe), 33)
        series = [it["pe"]["serie"] for it in self.pe]
        self.assertEqual(len(series), len(set(series)))
        for it in self.pe:
            p = it["pe"]
            self.assertEqual(it["cr"][0], "Ceasa-PE")
            self.assertIsNone(it["cr"][3])   # licença de republicação pendente
            if p["sem"]:
                self.assertIsNone(it["v"])
                self.assertIsNone(it["chg"])
                self.assertFalse(p["calc"])
            else:
                self.assertEqual(it["v"], p["comum"], it["key"])
                self.assertLessEqual(p["min"], p["comum"])
                self.assertLessEqual(p["comum"], p["max"])
            if FAIXA.search(p["embalagem"] or ""):
                self.assertFalse(p["calc"], it["key"])
                self.assertIsNone(p["rs_kg"], it["key"])
                self.assertNotEqual(it["unit"], "R$/kg", it["key"])
            if it.get("d"):
                self.assertIn(dt.date.fromisoformat(it["d"]).strftime("%d/%m/%Y"), p["url"])
            hist = json.loads((ROOT / "hist" / f"{it['key']}.json").read_text(encoding="utf-8"))
            self.assertEqual(hist["key"], it["key"])
            self.assertEqual(hist["rolls"], [])
            for dia, valor in hist["h"]:
                self.assertIsInstance(valor, (int, float))
                self.assertGreater(valor, 0)
                self.assertGreaterEqual(dia, "2026-10-01")
            if it["v"] is not None:
                self.assertEqual(dict(hist["h"]).get(it["d"]), it["v"], it["key"])

    def test_tomate_extra_e_caixa(self):
        extra = self.by["pe_tomate_extra"]
        self.assertEqual(extra["unit"], "R$/cx")
        self.assertIsNone(extra["pe"]["rs_kg"])
        self.assertIn("25 a 28 kg", extra["pe"]["unid"])
        limao = self.by["pe_limao_taiti"]
        self.assertNotIn("kg", limao["pe"]["unid"])
        self.assertFalse(limao["pe"]["calc"])

    def test_pagina_e_alertas(self):
        self.assertIn("function hortiLabel()", self.html)
        self.assertIn('?"Hortifrúti":"Hortifrúti (Ceagesp)"', self.html)
        self.assertIn("· por praça", self.html)
        self.assertIn("res.ok", self.html)
        self.assertNotIn("ck>=e", self.html)
        self.assertIn("calculado (peso publicado)", self.html)
        self.assertIn("Licença de republicação pendente", self.html)
        self.assertNotIn("licença concedida", self.html.lower())
        self.assertTrue(all(not str(a.get("key", "")).startswith("pe_") for a in self.data["alerts"]))
        ceasa = next(c for c in self.data["srcs"] if c[0] == "Ceasa-PE")
        self.assertIsNone(ceasa[3])
        sw = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn('const CORE = ["./icon-192.png", "./badge-96.png"];', sw)
        core = sw.split("const CORE = ", 1)[1].split(";", 1)[0]
        self.assertNotIn("index.html", core)
        self.assertNotIn('"./"', core)
        diff = subprocess.check_output(["git", "diff", "--name-only", "origin/main"], cwd=ROOT, text=True)
        for nome in ("news.json", "news_v2.json", "data.json", "alerts.json", "og-image.jpg"):
            self.assertNotIn(nome, diff.split())
        self.assertFalse((ROOT / "og-image.png").exists())
        self.assertTrue((ROOT / "og-image.jpg").is_file())
        added = subprocess.check_output(["git", "diff", "--name-only", "--diff-filter=A", "origin/main"], cwd=ROOT, text=True)
        self.assertNotIn("og-image.png", added.split())


if __name__ == "__main__":
    unittest.main()
