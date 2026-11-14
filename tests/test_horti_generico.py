"""Catálogo das praças (horti/mercados.json) e textos da página. Não inventa cotação e não fala com a rede.
14/11/2026: os testes de horti/regras.py e horti/montar_previa.py saíram (os módulos não estão mais no repositório)."""
from __future__ import annotations

import unittest

from _comum import ROOT, load, pagina

PRACAS = ["sp", "recife", "campinas", "bh", "cwb", "londrina", "maringa", "cascavel", "foz", "poa", "rj", "go", "sc", "df", "dfat", "vitoria"]


class Catalogo(unittest.TestCase):
    def test_pracas_do_pacote(self):
        doc = load(ROOT / "horti" / "mercados.json")
        self.assertFalse(doc["integracao_gerador"])
        self.assertEqual([p["id"] for p in doc["pracas"]], PRACAS)
        por = {p["id"]: p for p in doc["pracas"]}
        self.assertIsNone(por["sp"]["data"])
        self.assertFalse(por["vitoria"]["coleta_diaria"])   # Vitória: leitura manual, sem coletor
        self.assertNotIn("2026-10-27", por["cwb"]["dias"])
        self.assertIn("2026-11-02", por["londrina"]["dias"])
        for p in doc["pracas"]:
            self.assertNotIn("v", p)
            self.assertNotIn("comum", p)
            self.assertNotIn("min", p)
            self.assertIsNone(p["licenca"])   # acesso público não é licença
            if p["id"] != "sp":
                self.assertEqual(p["cotacoes"], "sim")
                self.assertIsNotNone(p["data"])
        self.assertEqual(doc["conab"]["cotacoes"], "nenhuma")
        self.assertIsNone(doc["conab"].get("data"))
        self.assertIn("citada a fonte", doc["conab"]["licenca"])
        self.assertEqual(doc["hf_brasil"]["registros"], 0)
        self.assertEqual(doc["hf_brasil"]["autorizacao_series"], "pendente")

    def test_pagina(self):
        html, data = pagina()
        self.assertIn("function hortiPinta()", html)
        self.assertIn("R$/kg da fonte", html)
        self.assertIn("mesmo preço há ", html)
        self.assertIn("Acesso público não é licença", html)
        self.assertNotIn("licença concedida", html.lower())
        horti = [it for it in data["items"] if str(it.get("key", "")).startswith(("cg_", "pe_")) or it.get("pe")]
        blob = " ".join(it["name"] + " " + str(it.get("src", "")) + " " + str(it.get("sub", "")) for it in horti)
        for proibido in ("Campinas", "Belo Horizonte", "Curitiba", "Londrina", "Maringá", "Cascavel", "Foz do Iguaçu", "Porto Alegre", "Goiânia", "São José"):
            self.assertNotIn(proibido, blob)


if __name__ == "__main__":
    unittest.main()
