"""Regras da prévia Ceasa-PE (Recife). Não fala com a rede e não publica."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "horti"))
import regras  # noqa: E402


def data():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    obj, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    return html, obj


class Regras(unittest.TestCase):
    def test_peso_exato_e_faixa(self):
        self.assertEqual(regras.peso_exato("KG"), 1)
        self.assertEqual(regras.peso_exato("CX 10KG"), 10)
        self.assertEqual(regras.peso_exato("SC.25 KG"), 25)
        self.assertEqual(regras.peso_exato("MOLHO 0,415 KG"), 0.415)
        for u in ["CX 25-28KG", "CX.13A14", "MOLHO 0,8-1KG", "SACO 18-20KG", "CX 22a23KG", "CX.25a27", "CENTO", "UNID.", "50 ESPIGAS"]:
            self.assertIsNone(regras.peso_exato(u), u)

    def test_zero_nao_e_preco(self):
        self.assertIsNone(regras.brl("R$ 0,00"))
        self.assertIsNone(regras.brl(""))
        self.assertEqual(regras.brl("R$ 1.071,00"), 1071.0)
        self.assertIsNone(regras.variacao(0, 10))
        self.assertIsNone(regras.variacao(10, None))
        self.assertIsNone(regras.variacao(None, 10))

    def test_faixa_nao_vira_media(self):
        valor, txt = regras.rs_kg(220, "CX 25-28KG")
        self.assertIsNone(valor)
        self.assertIsNone(txt)
        valor, txt = regras.rs_kg(40, "CX.25KG")
        self.assertEqual(valor, 1.6)
        self.assertIn("calculado", txt)
        valor, txt = regras.rs_kg(1.4, "KG")
        self.assertEqual(txt, "nativo R$/kg")


class Boletim(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.doc = json.loads((ROOT / "horti" / "ceasa-pe.json").read_text(encoding="utf-8"))
        cls.regs = cls.doc["registros"]

    def test_contagem_06_11(self):
        dia = [r for r in self.regs if r["data"] == "2026-11-06"]
        self.assertEqual(len(dia), 164)
        self.assertEqual(sum(1 for r in dia if not r["sem_cotacao"] and r["comum"] is not None), 140)
        self.assertEqual(self.doc["contagem"]["2026-11-06"], {"linhas": 164, "com_preco": 140})
        self.assertFalse(self.doc["coleta_diaria"])
        self.assertEqual(self.doc["licenca"], "pendente")

    def test_serie_unica_e_sem_zero(self):
        for dia in ("2026-11-05", "2026-11-06"):
            rows = [r for r in self.regs if r["data"] == dia]
            series = [r["serie"] for r in rows]
            self.assertEqual(len(series), len(set(series)))
        for r in self.regs:
            self.assertNotEqual(r["comum"], 0)
            self.assertEqual(r["sem_cotacao"], r["comum"] is None)
            kg = regras.peso_exato(r["embalagem"])
            valor, txt = regras.rs_kg(None if r["sem_cotacao"] else r["comum"], r["embalagem"])
            self.assertEqual(r["kg_embalagem"], kg)
            self.assertEqual(r["rs_kg_comum"], valor)
            self.assertEqual(r["rs_kg_calculo"], txt)
            if kg is None:
                self.assertIsNone(r["rs_kg_comum"])

    def test_casos_do_boletim(self):
        def um(produto, variedade, data="2026-11-06"):
            hits = [r for r in self.regs if r["data"] == data and r["produto"] == produto and r["variedade"] == variedade]
            self.assertEqual(len(hits), 1, (produto, variedade, len(hits)))
            return hits[0]

        tom = um("TOMATE", "EXTRA")
        self.assertEqual((tom["min"], tom["comum"], tom["max"], tom["embalagem"]), (210, 220, 230, "CX 25-28KG"))
        self.assertIsNone(tom["rs_kg_comum"])
        self.assertEqual(tom["comum"], 220)
        uva = um("UVA", "ITALIA")
        self.assertIn("14-18", uva["embalagem"].replace(" ", ""))
        self.assertIsNone(uva["rs_kg_comum"])
        self.assertEqual(uva["comum"], 120)
        tg = um("TANGERINA", "CRAVO")
        self.assertEqual(tg["rs_kg_comum"], 1.6)
        self.assertIn("calculado", tg["rs_kg_calculo"])
        self.assertEqual(tg["comum"], 40)
        self.assertTrue(um("UVA ISABEL", "PRETA")["sem_cotacao"])
        self.assertTrue(um("TANGERINA", "MURCOTT")["sem_cotacao"])
        self.assertIsNone(um("LIMÃO TAITI", "-")["rs_kg_comum"])


class Pagina(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.data = data()
        cls.by = {it["key"]: it for it in cls.data["items"]}
        cls.doc = json.loads((ROOT / "horti" / "ceasa-pe.json").read_text(encoding="utf-8"))
        cls.boletim = {r["serie"]: r for r in cls.doc["registros"] if r["data"] == "2026-11-06"}

    def test_precos_que_ja_existiam(self):
        self.assertEqual(self.by["cg_tomate"]["v"], 14.44)
        self.assertEqual(self.by["cg_tomate"]["chg"], 3.9597)
        self.assertEqual(self.by["cg_tomate"]["unit"], "R$/kg")
        self.assertEqual(self.by["soja"]["v"], 158.52)
        self.assertEqual(self.by["boi_SP"]["v"], 391.67)
        self.assertNotIn("h", self.by["cg_tomate"])
        self.assertNotIn("rolls", self.by["soja"])
        self.assertTrue(all("h" not in it and "rolls" not in it for it in self.data["items"]))

    def test_lista_curada_nao_mistura(self):
        pe = [it for it in self.data["items"] if it.get("pe")]
        self.assertEqual(len(pe), 33)
        series = []
        for it in pe:
            p = it["pe"]
            series.append(p["serie"])
            src = self.boletim[p["serie"]]
            self.assertEqual(p["embalagem"], src["embalagem"])
            self.assertEqual(p["variedade"], src["variedade"])
            self.assertEqual(p["procedencia"], src["procedencia"])
            self.assertEqual(p["min"], src["min"])
            self.assertEqual(p["comum"], src["comum"])
            self.assertEqual(p["max"], src["max"])
            self.assertEqual(it["cr"][3], None)
            self.assertEqual(it["cr"][0], "Ceasa-PE")
            self.assertFalse(p["coleta_diaria"])
            if p["sem"]:
                self.assertIsNone(it["v"])
                self.assertIsNone(it["chg"])
                self.assertFalse(p["calc"])
            else:
                self.assertEqual(it["v"], src["comum"])
                anterior = next(r for r in self.doc["registros"] if r["serie"] == p["serie"] and r["data"] == "2026-11-05")
                prev = None if anterior["sem_cotacao"] else anterior["comum"]
                self.assertEqual(it["chg"], regras.variacao(src["comum"], prev))
            if regras.peso_exato(p["embalagem"]) is None:
                self.assertFalse(p["calc"])
                self.assertIsNone(p["rs_kg"])
                self.assertNotEqual(it["unit"], "R$/kg")
            hist = json.loads((ROOT / "hist" / f"{it['key']}.json").read_text(encoding="utf-8"))
            self.assertEqual(hist["key"], it["key"])
            self.assertEqual(hist["rolls"], [])
            for dia, valor in hist["h"]:
                self.assertIsInstance(valor, (int, float))
                self.assertGreater(valor, 0)
                rec = next(r for r in self.doc["registros"] if r["serie"] == p["serie"] and r["data"] == dia)
                self.assertEqual(valor, rec["comum"])
        self.assertEqual(len(series), len(set(series)))

    def test_tomate_uva_tangerina_limao(self):
        extra = self.by["pe_tomate_extra"]
        self.assertEqual(extra["v"], 220)
        self.assertEqual(extra["unit"], "R$/cx")
        self.assertIsNone(extra["pe"]["rs_kg"])
        self.assertIn("25 a 28 kg", extra["pe"]["unid"])
        uva = self.by["pe_uva_italia"]
        self.assertEqual(uva["v"], 120)
        self.assertIsNone(uva["pe"]["rs_kg"])
        self.assertIn("14 a 18 kg", uva["pe"]["unid"])
        cravo = self.by["pe_tangerina_cravo"]
        self.assertEqual(cravo["v"], 40)
        self.assertEqual(cravo["unit"], "R$/cx")
        self.assertTrue(cravo["pe"]["calc"])
        self.assertEqual(cravo["pe"]["rs_kg"], 1.6)
        self.assertIsNone(self.by["pe_uva_isabel"]["v"])
        self.assertIsNone(self.by["pe_tangerina_murcott"]["chg"])
        limao = self.by["pe_limao_taiti"]
        self.assertEqual(limao["v"], 200)
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
        for nome in ("news.json", "news_v2.json", "data.json", "alerts.json", "og-image.png", "og-image.jpg"):
            self.assertNotIn(nome, diff.split())


if __name__ == "__main__":
    unittest.main()
