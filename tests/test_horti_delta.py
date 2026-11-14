"""Boletins de hortifrúti publicados (horti/). Não baixa boletim e não fala com a rede.
14/11/2026: o coletor e as regras (horti/coleta_staging.py, regras.py, indice/) rodam fora do repositório desde 09/11;
os testes conferem o que está publicado, sem fixar a última data (a coleta diária acrescenta dias)."""
from __future__ import annotations

import json
import unittest

from _comum import ROOT, boletins, load, pagina


class Delta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quarentena = load(ROOT / "horti" / "quarentena.json")
        cls.boletins = boletins()

    def test_quarentena_fica_de_fora(self):
        self.assertEqual(len(self.quarentena), 129)
        chaves = {(q["serie"], q["data"]) for q in self.quarentena}
        self.assertEqual(len(chaves), 129)
        for q in self.quarentena:
            precos = {tuple(p) for p in q["precos"]}
            self.assertGreater(len(precos), 1, q["serie"])
            self.assertIn("setembro27092026.pdf", q["arquivos"])
            self.assertIn("outubro27102026.pdf", q["arquivos"])
        for doc in self.boletins.values():
            for r in doc["registros"]:
                self.assertNotIn((r["serie"], r["data"]), chaves)

    def test_pares_iguais_guardam_a_segunda_proveniencia(self):
        n = 0
        for doc in self.boletins.values():
            for r in doc["registros"]:
                extra = r.get("proveniencia_extra") or []
                if not extra:
                    continue
                n += 1
                nomes = [x.get("arquivo") for x in extra]
                self.assertIn("setembro27092026.pdf", nomes)
                self.assertNotEqual(r.get("arquivo"), "setembro27092026.pdf")
        self.assertEqual(n, 117)

    def test_datas_sao_as_do_boletim(self):
        for nome, doc in self.boletins.items():
            datas = doc["datas"]
            self.assertEqual(datas, sorted(set(datas)), nome)
            self.assertEqual(set(datas), {r["data"] for r in doc["registros"]}, nome)
        # dias que já estavam publicados continuam; lacunas não são preenchidas
        self.assertLessEqual(
            {"2026-10-26", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"},
            set(self.boletins["cwb"]["datas"]),
        )
        self.assertNotIn("2026-10-27", self.boletins["cwb"]["datas"])
        self.assertIn("2026-11-02", self.boletins["londrina"]["datas"])
        for d in ("2026-11-05", "2026-11-06"):
            self.assertNotIn(d, self.boletins["foz"]["datas"])

    def test_faixa_do_rs_e_preco_nativo_de_goias(self):
        pimentao = next(
            r for r in self.boletins["poa"]["registros"]
            if r["data"] == "2026-11-06" and r["produto"] == "Pimentão Vermelho" and r["max"] == 200
        )
        self.assertEqual((pimentao["min"], pimentao["comum"]), (15, 17))
        self.assertIn("faixa_em_conferencia", pimentao["flags"])
        incoerentes = [r for doc in self.boletins.values() for r in doc["registros"] if r.get("fora_da_variacao")]
        self.assertGreaterEqual(len(incoerentes), 8)
        agriao = next(r for r in self.boletins["go"]["registros"] if "AGRI" in r["produto"].upper())
        self.assertIsNone(agriao["rs_kg_fonte"])
        self.assertIsNone(agriao["rs_kg_calc"])

    def test_vitoria_e_manual_e_hf_nao_entra(self):
        es = self.boletins["vitoria"]
        self.assertEqual(es["datas"], ["2026-11-05", "2026-11-06"])
        self.assertTrue(all(r["manual"] for r in es["registros"]))
        self.assertTrue(all(r["url_publica"] == "https://ceasa.es.gov.br/bancodedados" for r in es["registros"]))
        self.assertFalse(any(p.suffix == ".pdf" for p in (ROOT / "horti").rglob("*")))
        fontes = {r["fonte"] for doc in self.boletins.values() for r in doc["registros"]}
        self.assertFalse(any("hf" in f.lower() or "cepea" in f.lower() for f in fontes))

    def test_filtro_nao_derruba_hortifruti(self):
        rows = [r for doc in self.boletins.values() for r in doc["registros"]]
        self.assertTrue(any("COUVE" in r["produto"].upper() and "FLOR" in r["produto"].upper() for r in rows))
        self.assertTrue(any("MANGA" in r["produto"].upper() and "ROSA" in (r.get("variedade") or r["produto"]).upper() for r in rows))
        self.assertGreater(len([r for r in rows if r["produto"].upper() in {"PINHAO", "PINHÃO"}]), 0)
        self.assertFalse(any("ver backfill_log.json" in json.dumps(r, ensure_ascii=False) for r in rows))

    @unittest.expectedFailure
    def test_flor_nao_entra(self):
        """Bug conhecido (14/11/2026): desde 10/11 o coletor diário (fora do repositório) deixa passar flores
        (ORQUIDEA) no boletim de Curitiba; o pacote auditado de 07/11 tirava. Não aparece em DATA."""
        rows = [r for doc in self.boletins.values() for r in doc["registros"]]
        self.assertFalse(any("ORQUIDEA" in r["produto"].upper() for r in rows))

    @unittest.expectedFailure
    def test_pitaia_nao_vira_pinhao(self):
        """Bug conhecido (14/11/2026): desde 10/11 o coletor diário (fora do repositório) grava Pitaia (cx 4 kg) como
        produto «Pinhão» com variedade PITAIA em cwb, londrina e foz. Não aparece em DATA. Quando o coletor for
        corrigido este teste passa e o expectedFailure deve sair."""
        rows = [r for doc in self.boletins.values() for r in doc["registros"]]
        pinhao = [r for r in rows if r["produto"].upper() in {"PINHAO", "PINHÃO"}]
        self.assertTrue(all("PITAIA" not in (r.get("variedade") or "").upper() for r in pinhao))

    def test_ponto_incoerente_nao_entra_no_historico(self):
        bloqueio = {
            (r["serie"], r["data"])
            for doc in self.boletins.values() for r in doc["registros"] if r.get("fora_da_variacao")
        }
        _, data = pagina()
        for it in data["items"]:
            pack = it.get("hf")
            if not pack:
                continue
            hist = load(ROOT / "hist" / f"{it['key']}.json")
            for dia, _valor in hist["h"]:
                self.assertNotIn((pack["serie"], dia), bloqueio)

    def test_coletor_fica_fora_do_repositorio(self):
        """Substitui o teste antigo de horti/coleta_staging.py (removido do repositório em 09/11)."""
        self.assertEqual(sorted(p.name for p in (ROOT / "horti").rglob("*.py")), [])
        self.assertFalse((ROOT / "horti" / "indice").exists())
        doc = load(ROOT / "horti" / "mercados.json")
        self.assertFalse(doc["integracao_gerador"])


if __name__ == "__main__":
    unittest.main()
