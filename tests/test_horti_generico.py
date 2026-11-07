"""Camada genérica das praças. Não inventa cotação e não fala com a rede."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "horti"))
import regras  # noqa: E402


class Conta(unittest.TestCase):
    def test_zero_sc_e_vazio(self):
        for bruto in ("R$ 0,00", "0,00", "0.00", "0", "", "S/C", "s/ cotação", "s/cotação", None):
            self.assertIsNone(regras.cotacao(bruto), bruto)
        self.assertEqual(regras.cotacao("R$ 220,00"), 220)
        self.assertEqual(regras.cotacao("17,00"), 17)
        self.assertIsNone(regras.variacao(None, 10))
        self.assertIsNone(regras.variacao(0, 10))

    def test_serie_nao_mistura_classificacao(self):
        a = regras.serie_generica("curitiba", "TOMATE", "longa vida", "extra A", "CX 20KG", "PR")
        b = regras.serie_generica("curitiba", "TOMATE", "longa vida", "especial", "CX 20KG", "PR")
        c = regras.serie_generica("londrina", "TOMATE", "longa vida", "extra A", "CX 20KG", "PR")
        self.assertNotEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertEqual(a, regras.serie_generica("curitiba", "TOMATE", "longa vida", "extra A", "CX 20KG", "PR"))

    def test_coluna_ceagesp_do_noticias_agricolas_fica_de_fora(self):
        self.assertFalse(regras.usar_cotacao("noticias_agricolas", "Ceagesp"))
        self.assertFalse(regras.usar_cotacao("noticias_agricolas", "São Paulo"))
        self.assertTrue(regras.usar_cotacao("noticias_agricolas", "Campinas"))
        self.assertTrue(regras.usar_cotacao("ceasa_pe", "Ceagesp"))

    def test_quilo_nativo_separado_do_calculado(self):
        faixa = regras.papel_kg("CX 25-28KG", None, 220)
        self.assertIsNone(faixa["nativo"])
        self.assertIsNone(faixa["calculado"])
        self.assertEqual(faixa["preco"], 220)
        self.assertNotEqual(round(220 / 26.5, 2), faixa["calculado"])
        nativo = regras.papel_kg("KG", 3.5, 3.5)
        self.assertEqual(nativo["nativo"], 3.5)
        self.assertIsNone(nativo["calculado"])
        calc = regras.papel_kg("CX 25KG", None, 40)
        self.assertIsNone(calc["nativo"])
        self.assertEqual(calc["calculado"], 1.6)
        self.assertIn("calculado", calc["texto"])
        molho = regras.papel_kg("MOLHO", 0, 5)
        self.assertEqual(molho["preco"], 5)
        self.assertIsNone(molho["nativo"])
        self.assertIsNone(molho["calculado"])
        coluna = regras.papel_kg("CX 22KG", 12.27, 270)
        self.assertEqual(coluna["nativo"], 12.27)
        self.assertEqual(coluna["preco"], 270)
        self.assertIsNone(coluna["calculado"])

    def test_alerta_so_na_mesma_serie(self):
        tomate = regras.serie_generica("recife", "TOMATE", "EXTRA", "", "CX 25-28KG", "PE")
        outra = regras.serie_generica("recife", "TOMATE", "ESPECIAL", "", "CX 25-28KG", "PE")
        self.assertIsNone(regras.alerta(tomate, 260, outra, 200))
        self.assertIsNone(regras.alerta(tomate, None, tomate, 200))
        self.assertIsNone(regras.alerta(tomate, 220, tomate, 210))
        self.assertAlmostEqual(regras.alerta(tomate, 250, tomate, 200), 25)

    def test_repeticao_nao_atrasa_a_data(self):
        dias = [("2026-11-0%d" % i, 7.0) for i in range(2, 7)]
        r = regras.repeticoes(dias)
        self.assertEqual(r["n"], 5)
        self.assertFalse(r["atrasado"])
        self.assertEqual(r["data"], "2026-11-06")
        mudou = regras.repeticoes(dias[:-1] + [("2026-11-06", 8.0)])
        self.assertEqual(mudou["n"], 1)
        self.assertEqual(mudou["data"], "2026-11-06")
        self.assertFalse(mudou["atrasado"])

    def test_acesso_publico_nao_e_licenca(self):
        self.assertIsNone(regras.licenca(None))
        self.assertIsNone(regras.licenca("  "))
        self.assertEqual(regras.licenca("citação obrigatória"), "citação obrigatória")


class Catalogo(unittest.TestCase):
    def test_pracas_do_pacote(self):
        doc = json.loads((ROOT / "horti" / "mercados.json").read_text(encoding="utf-8"))
        self.assertFalse(doc["coleta_diaria"])
        self.assertFalse(doc["integracao_gerador"])
        ids = [p["id"] for p in doc["pracas"]]
        self.assertEqual(
            ids,
            ["sp", "recife", "campinas", "bh", "cwb", "londrina", "maringa", "cascavel", "foz", "poa", "rj", "go", "sc", "df", "dfat", "vitoria"],
        )
        por = {p["id"]: p for p in doc["pracas"]}
        self.assertEqual(por["recife"]["data"], "2026-11-06")
        self.assertIsNone(por["recife"]["licenca"])
        self.assertIsNone(por["sp"]["data"])
        self.assertEqual(por["foz"]["data"], "2026-11-04")
        self.assertEqual(por["vitoria"]["dias"], ["2026-11-05", "2026-11-06"])
        self.assertNotIn("2026-10-27", por["cwb"]["dias"])
        self.assertIn("2026-11-02", por["londrina"]["dias"])
        self.assertEqual(len(por["londrina"]["dias"]), 10)
        for p in doc["pracas"]:
            self.assertNotIn("v", p)
            self.assertNotIn("comum", p)
            self.assertNotIn("min", p)
            self.assertIsNone(p["licenca"])
            if p["id"] != "sp":
                self.assertEqual(p["cotacoes"], "sim")
                self.assertIsNotNone(p["data"])
        self.assertEqual(doc["conab"]["cotacoes"], "nenhuma")
        self.assertIsNone(doc["conab"].get("data"))
        self.assertIn("citada a fonte", doc["conab"]["licenca"])
        self.assertEqual(doc["conab"]["periodo"], "setembro/2026")
        self.assertEqual(doc["hf_brasil"]["registros"], 0)
        self.assertEqual(doc["hf_brasil"]["autorizacao_series"], "pendente")
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        self.assertIn("function hortiPinta()", html)
        self.assertIn("Cotações do pacote de 07/11/2026", html)
        self.assertIn("R$/kg da fonte", html)
        self.assertIn("mesmo preço há ", html)
        self.assertIn("Acesso público não é licença", html)
        self.assertNotIn("licença concedida", html.lower())
        self.assertIn("/*HPE prévia:", html)
        sys.path.insert(0, str(ROOT / "horti"))
        import montar_previa  # noqa: E402
        self.assertEqual(montar_previa.apply_ui(html, []), html)
        i = html.find("const DATA=")
        data, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
        horti = [it for it in data["items"] if str(it.get("key", "")).startswith(("cg_", "pe_")) or it.get("pe")]
        blob = " ".join(it["name"] + " " + str(it.get("src", "")) + " " + str(it.get("sub", "")) for it in horti)
        for proibido in ("Campinas", "Belo Horizonte", "Curitiba", "Londrina", "Maringá", "Cascavel", "Foz do Iguaçu", "Porto Alegre", "Goiânia", "São José"):
            self.assertNotIn(proibido, blob)


if __name__ == "__main__":
    unittest.main()
