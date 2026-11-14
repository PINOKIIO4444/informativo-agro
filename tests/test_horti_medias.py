"""Média da semana e do mês saem só dos dias da cotação. O detalhe de Recife sai do hist."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _comum import medias_civis  # noqa: E402  (14/11: horti/regras.py saiu do repositório em 09/11)


def _data():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    obj, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    return html, {it["key"]: it for it in obj["items"]}


def _ref():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    obj, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    return obj["ref"]


def _medias_js(html: str) -> str:
    i = html.find("function mediasCivis")
    j = html.find("function renderDet", i)
    if i < 0 or j < 0:
        raise AssertionError("mediasCivis ausente")
    return html[i:j]


class MediasCivis(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.html, cls.itens = _data()

    def test_medias_do_hortifruti_saem_do_hist(self):
        """Semana/mês civis (referência do informativo ou data da série, a mais recente), só com dias que têm preço;
        o preço do dia não muda."""
        self.ref = _ref()
        n = 0
        for k, x in self.itens.items():
            if not k.startswith(("pe_", "hf_")) or not x.get("d"):
                continue
            hist = json.loads((ROOT / "hist" / f"{k}.json").read_text(encoding="utf-8"))
            if not hist["h"]:
                continue
            n += 1
            self.assertEqual(hist["rolls"], [])
            self.assertEqual(x["first"], hist["h"][0][0], k)
            self.assertEqual(x["n"], len(hist["h"]), k)
            civ = medias_civis(hist["h"], max(x["d"], self.ref))   # referência do informativo ou da série, a mais recente
            self.assertEqual((x.get("wkn"), x.get("mon")), (civ["wkn"], civ["mon"]), k)
            for campo in ("wk", "mo"):
                if civ[campo] is None:
                    self.assertIsNone(x.get(campo), k)
                else:
                    self.assertAlmostEqual(x[campo], civ[campo], places=3, msg=k)
            if x.get("v") is not None:
                ultimo = dict(hist["h"]).get(x["d"])
                self.assertEqual(x["v"], ultimo, k)
        self.assertGreater(n, 100)

    def test_conta_recusa_dia_de_fora(self):
        pontos = [["2026-10-30", 50], ["2026-11-01", 100], ["2026-11-03", 200], ["2026-11-06", 400]]
        civ = medias_civis(pontos, "2026-11-06")
        self.assertEqual((civ["wkn"], civ["wk"], civ["mon"]), (2, 300, 3))
        self.assertAlmostEqual(civ["mo"], 700 / 3, places=4)

    def test_brasilia_duplicada_permanece(self):
        self.assertIn("hf_df_tomate", self.itens)
        self.assertIn("hf_dfat_tomate", self.itens)

    def test_template_calcula_no_historico_e_rejeita_dia_de_fora(self):
        self.assertIn("function mediasCivis", self.html)
        self.assertIn("wkC", self.html)
        self.assertIn("moC", self.html)
        self.assertIn("const nn=hd.length||x.n", self.html)
        self.assertNotIn("${mv(x.wk,x.dec,x)}", self.html)
        self.assertNotIn("${mv(x.mo,x.dec,x)}", self.html)
        fn = _medias_js(self.html)
        fixture = (
            '[["2026-10-30",50],["2026-11-01",100],["2026-11-03",200],["2026-11-06",400]]'
        )
        gate = (
            fn
            + "const r=mediasCivis("
            + fixture
            + ',"2026-11-06",[]);'
            + "const ok=r.wkn===2&&r.mon===3&&Math.abs(r.wk-300)<1e-6&&Math.abs(r.mo-700/3)<1e-6;"
            + "if(!ok){console.error(JSON.stringify(r));process.exit(2)}"
        )
        bom = subprocess.run(["node", "-e", gate], capture_output=True, text=True)
        self.assertEqual(bom.returncode, 0, bom.stderr)
        rolagem = """
function mediasCivis(pontos,data,rolls){
 const fim=new Date(data+"T12:00:00Z");
 const d7=new Date(fim);d7.setUTCDate(fim.getUTCDate()-6);
 const d31=new Date(fim);d31.setUTCDate(fim.getUTCDate()-30);
 const sem=pontos.filter(p=>p[0]>=d7.toISOString().slice(0,10)&&p[0]<=data);
 const m=pontos.filter(p=>p[0]>=d31.toISOString().slice(0,10)&&p[0]<=data);
 const avg=xs=>xs.length?xs.reduce((s,p)=>s+Number(p[1]),0)/xs.length:null;
 return {wk:avg(sem),wkn:sem.length,mo:avg(m),mon:m.length,first:pontos[0][0],n:pontos.length}}
"""
        ruim = subprocess.run(["node", "-e", rolagem + gate[len(fn):]], capture_output=True, text=True)
        self.assertNotEqual(ruim.returncode, 0)

    def test_data_sem_serie_e_coleta_desligada(self):
        for it in self.itens.values():
            self.assertNotIn("h", it)
            self.assertNotIn("rolls", it)
        sw = (ROOT / "sw.js").read_text(encoding="utf-8")
        self.assertIn('const CACHE = PREFIX + "v27";', sw)
        self.assertIn('const CORE = ["./icon-192.png", "./badge-96.png"];', sw)
        nucleo = sw.split("const CORE = ", 1)[1].split(";", 1)[0]
        self.assertNotIn("index.html", nucleo)
        self.assertIn("caches.open(CACHE).then(c => c.addAll(CORE))", sw)
        self.assertIn("res.ok", self.html)
        self.assertIn("function scotLate38", self.html)
        self.assertNotIn('id="hortip"', self.html)
        quar = json.loads((ROOT / "horti" / "quarentena.json").read_text(encoding="utf-8"))
        self.assertEqual(len(quar), 129)


if __name__ == "__main__":
    unittest.main()
