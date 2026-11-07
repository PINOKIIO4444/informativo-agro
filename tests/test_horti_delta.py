"""Junção do pacote auditado. Não baixa boletim e não liga a coleta."""
from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


class Delta(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quarentena = load(ROOT / "horti" / "quarentena.json")
        cls.boletins = {}
        for path in (ROOT / "horti" / "boletins").glob("*.json"):
            cls.boletins[path.stem] = load(path)

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

    def test_dias_do_parana(self):
        self.assertEqual(
            self.boletins["cwb"]["datas"],
            ["2026-10-26", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-03", "2026-11-04", "2026-11-05", "2026-11-06"],
        )
        self.assertEqual(len(self.boletins["londrina"]["datas"]), 10)
        self.assertIn("2026-11-02", self.boletins["londrina"]["datas"])
        self.assertEqual(len(self.boletins["maringa"]["datas"]), 9)
        self.assertEqual(len(self.boletins["cascavel"]["datas"]), 9)
        self.assertEqual(
            self.boletins["foz"]["datas"],
            ["2026-10-26", "2026-10-27", "2026-10-28", "2026-10-29", "2026-10-30", "2026-11-03", "2026-11-04"],
        )

    def test_faixa_do_rs_e_preco_nativo_de_goias(self):
        pimentao = next(
            r for r in self.boletins["poa"]["registros"]
            if r["data"] == "2026-11-06" and r["produto"] == "Pimentão Vermelho" and r["max"] == 200
        )
        self.assertEqual((pimentao["min"], pimentao["comum"]), (15, 17))
        self.assertIn("faixa_em_conferencia", pimentao["flags"])
        incoerentes = [
            r for doc in self.boletins.values() for r in doc["registros"] if r.get("fora_da_variacao")
        ]
        self.assertGreaterEqual(len(incoerentes), 8)
        agriao = next(r for r in self.boletins["go"]["registros"] if "AGRI" in r["produto"].upper())
        self.assertEqual(agriao["comum"], 5)
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
        pinhao = [r for r in rows if r["produto"].upper() in {"PINHAO", "PINHÃO"}]
        self.assertGreater(len(pinhao), 0)
        self.assertTrue(all("PITAIA" not in (r.get("variedade") or "").upper() for r in pinhao))
        self.assertFalse(any("ORQUIDEA" in r["produto"].upper() for r in rows))
        self.assertFalse(any("ver backfill_log.json" in json.dumps(r, ensure_ascii=False) for r in rows))

    def test_ponto_incoerente_nao_entra_no_historico(self):
        bloqueio = {
            (r["serie"], r["data"])
            for doc in self.boletins.values() for r in doc["registros"] if r.get("fora_da_variacao")
        }
        html = (ROOT / "index.html").read_text(encoding="utf-8")
        i = html.find("const DATA=")
        data, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
        for it in data["items"]:
            pack = it.get("hf")
            if not pack:
                continue
            hist = load(ROOT / "hist" / f"{it['key']}.json")
            for dia, _valor in hist["h"]:
                self.assertNotIn((pack["serie"], dia), bloqueio)

    def test_indice_resolve_mes_e_ano_e_a_coleta_fica_desligada(self):
        sys.path.insert(0, str(ROOT / "horti"))
        import coleta_staging
        self.assertFalse(coleta_staging.ATIVO)
        with self.assertRaises(SystemExit):
            coleta_staging.executar("2026-11-06")
        proc = subprocess.run([sys.executable, "test_indices.py"], cwd=ROOT / "horti" / "indice", capture_output=True, text=True)
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertGreaterEqual(proc.stdout.count("OK"), 15)


if __name__ == "__main__":
    unittest.main()
