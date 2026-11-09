"""Média da semana e do mês saem só dos dias da cotação. O detalhe de Recife sai do hist."""
from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
import sys

sys.path.insert(0, str(ROOT / "horti"))
import regras  # noqa: E402


def _data():
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    i = html.find("const DATA=")
    obj, _ = json.JSONDecoder().raw_decode(html, i + len("const DATA="))
    return html, {it["key"]: it for it in obj["items"]}


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

    def test_tomate_curitiba_mes_e_preco_do_dia(self):
        x = self.itens["hf_cwb_tomate"]
        self.assertEqual(x["v"], 260.0)
        self.assertEqual(x["d"], "2026-11-06")
        self.assertEqual(x["mo"], 232.5)
        self.assertEqual(x["mon"], 4)
        self.assertEqual(x["wk"], 232.5)
        self.assertEqual(x["wkn"], 4)

    def test_foz_semana_so_com_os_dias_da_semana(self):
        x = self.itens["hf_foz_tomate"]
        self.assertEqual(x["v"], 260.0)
        self.assertEqual(x["d"], "2026-11-04")
        self.assertEqual(x["wk"], 260.0)
        self.assertEqual(x["wkn"], 2)

    def test_recife_detalhe_sai_do_historico(self):
        x = self.itens["pe_tomate_extra"]
        hist = json.loads((ROOT / "hist" / "pe_tomate_extra.json").read_text(encoding="utf-8"))
        self.assertEqual(x["v"], 220.0)
        self.assertEqual(x["first"], hist["h"][0][0])
        self.assertEqual(x["n"], len(hist["h"]))
        self.assertEqual(x["first"], "2026-10-26")
        self.assertEqual(x["n"], 8)
        self.assertEqual(x["mon"], 4)
        self.assertEqual(x["mo"], 210.0)
        oito = [
            k for k, it in self.itens.items()
            if k.startswith("pe_") and it.get("n") == 8 and it.get("first") == "2026-10-26"
        ]
        self.assertEqual(len(oito), 21)

    def test_soja_e_ceagesp_continuam_iguais(self):
        soja = self.itens["soja"]
        self.assertEqual(soja["wk"], 158.625)
        self.assertEqual(soja["wkn"], 4)
        self.assertEqual(soja["mo"], 158.625)
        self.assertEqual(soja["mon"], 4)
        self.assertEqual(soja["n"], 1709)
        self.assertEqual(soja["first"], "2020-01-02")
        self.assertEqual(soja["v"], 158.52)
        cg = self.itens["cg_tomate"]
        self.assertEqual(cg["wk"], 14.165)
        self.assertEqual(cg["wkn"], 2)
        self.assertEqual(cg["mo"], 14.165)
        self.assertEqual(cg["mon"], 2)
        self.assertEqual(cg["v"], 14.44)

    def test_conta_recusa_dia_de_fora(self):
        pontos = [["2026-10-30", 50], ["2026-11-01", 100], ["2026-11-03", 200], ["2026-11-06", 400]]
        civ = regras.medias_civis(pontos, "2026-11-06")
        self.assertEqual(civ["wkn"], 2)
        self.assertEqual(civ["wk"], 300)
        self.assertEqual(civ["mon"], 3)
        self.assertAlmostEqual(civ["mo"], 700 / 3, places=4)
        cwb = json.loads((ROOT / "hist" / "hf_cwb_tomate.json").read_text(encoding="utf-8"))
        mes = regras.medias_civis(cwb["h"], "2026-11-06")
        self.assertEqual((mes["mo"], mes["mon"]), (232.5, 4))

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
