"""Cartão enxuto da lista de hortifrúti. O detalhe continua completo."""
from __future__ import annotations

import json
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML = (ROOT / "index.html").read_text(encoding="utf-8")


def _entre(html: str, ini: str, fim: str) -> str:
    i = html.find(ini)
    j = html.find(fim, i + len(ini))
    if i < 0 or j < 0:
        raise AssertionError(f"trecho ausente: {ini!r} … {fim!r}")
    return html[i:j]


class CartaoEnxuto(unittest.TestCase):
    def test_pagina_sem_filtro_de_praca(self):
        self.assertIn('id="hortiq"', HTML)
        self.assertIn('id="hortiprod"', HTML)
        self.assertNotIn('id="hortip"', HTML)
        self.assertNotIn('aria-label="Praça"', HTML)
        self.assertNotIn("hortiEscolhe", HTML)
        self.assertIn("#hortiprod{flex-wrap:wrap;overflow:visible;", HTML)
        self.assertIn("-webkit-mask-image:none;mask-image:none", HTML)
        pagina = _entre(HTML, "function hortiPage", "const HORTI_HEAD")
        self.assertLess(pagina.find('id="hortiq"'), pagina.find('id="hortiprod"'))
        self.assertLess(pagina.find('id="hortiprod"'), pagina.find('id="hortilist"'))
        self.assertIn("b.innerHTML=hortiLista()", pagina)

    def test_produto_lista_as_pracas_e_o_detalhe_guarda_o_resto(self):
        uni = _entre(HTML, "const UNI=", "const hoje49")
        funcoes = _entre(HTML, "function hortiNorm", "function peBolLinha")
        consts = _entre(HTML, "const HORTI_HEAD=", "const NAV=")
        i = HTML.find("const DATA=")
        data, _ = json.JSONDecoder().raw_decode(HTML, i + len("const DATA="))
        programa = r"""
const fmt=(v,d)=>v==null?"—":v.toLocaleString("pt-BR",{minimumFractionDigits:d,maximumFractionDigits:d});
const esc=s=>String(s==null?"":s);
const pl=()=>'<span class="pill">+1%</span>';
const pctX=()=>"alta de 1,00%";
const FX49=true;
let HORTI_Q="",HORTI_PRACA="",HORTI_PROD="tomate";
const I=Object.fromEntries(ITEMS.map(x=>[x.key,x]));
""" + uni + "\n" + funcoes + "\n" + consts + r"""
const els={};
global.document={getElementById(id){return els[id]||(els[id]={innerHTML:"",open:false});}};
function nomes(html){return [...html.matchAll(/<div class="n">([^<]*)<\/div>/g)].map(m=>m[1]);}
function hrefs(html){return [...html.matchAll(/href="#([^"]+)"/g)].map(m=>m[1]);}
HORTI_Q="";HORTI_PROD="tomate";
const lista=hortiLista();
const tomates=nomes(lista);
const chaves=hrefs(lista);
hortiPinta();
const chips=els.hortiprod.innerHTML;
const busca=(()=>{HORTI_Q="cx 20 kg";return hortiLista();})();
HORTI_Q="tomate";
const varios=hortiLista();
const curitiba=I.hf_cwb_tomate;
const detalhe=peLinha(curitiba);
const cartao=hortiRow(curitiba,"");
process.stdout.write(JSON.stringify({
  tomates, chaves, chips,
  busca: hrefs(busca),
  variosNomes: nomes(varios),
  variosHrefs: hrefs(varios),
  detalhe, cartao,
  recife: hortiRow(I.pe_tomate_extra,""),
  sp: hortiRow(I.cg_tomate,"")
}));
"""
        itens = [it for it in data["items"] if str(it.get("key", "")).startswith(("cg_", "pe_", "hf_"))]
        fonte = "const ITEMS=" + json.dumps(itens, ensure_ascii=False) + ";\n" + programa
        with tempfile.NamedTemporaryFile("w", suffix=".js", encoding="utf-8", delete=False) as tmp:
            tmp.write(fonte)
            caminho = tmp.name
        try:
            saida = subprocess.check_output(["node", caminho], cwd=ROOT, text=True)
        finally:
            Path(caminho).unlink(missing_ok=True)
        doc = json.loads(saida)
        self.assertEqual(
            doc["tomates"],
            [
                "São Paulo", "Recife", "Campinas", "Belo Horizonte", "Curitiba", "Londrina",
                "Maringá", "Cascavel", "Foz do Iguaçu", "Porto Alegre", "Rio de Janeiro",
                "Goiânia", "São José", "Brasília SIMA", "Brasília atacado", "Vitória",
            ],
        )
        self.assertEqual(len(doc["tomates"]), len(set(doc["tomates"])))
        self.assertIn("hf_cwb_tomate", doc["chaves"])
        self.assertIn("pe_tomate_extra", doc["chaves"])
        self.assertNotIn("pe_tomate_especial", doc["chaves"])
        self.assertNotIn("id=\"hortip\"", doc["chips"])
        self.assertNotIn("Recife", doc["chips"])
        self.assertIn("Tomate", doc["chips"])
        self.assertIn("Pimentão", doc["chips"])
        for proibido in ("mín.", "máx.", "PR, SP", "EXTRA A", "calculado", "Firme", "mesmo preço", "06/11", "07/11"):
            self.assertNotIn(proibido, doc["cartao"])
        self.assertIn('href="#hf_cwb_tomate"', doc["cartao"])
        self.assertIn("openDet('hf_cwb_tomate')", doc["cartao"])
        self.assertIn(">Curitiba<", doc["cartao"])
        self.assertIn("/cx", doc["cartao"])
        self.assertIn("/cx", doc["recife"])
        self.assertIn(">Recife<", doc["recife"])
        self.assertIn("/kg", doc["sp"])
        self.assertIn(">São Paulo<", doc["sp"])
        self.assertIn("hf_cwb_tomate", doc["busca"])
        self.assertIn("Recife · Extra", doc["variosNomes"])
        self.assertIn("Recife · Especial", doc["variosNomes"])
        self.assertIn("Recife · Primeira", doc["variosNomes"])
        self.assertIn("Recife · Segunda", doc["variosNomes"])
        self.assertEqual(doc["variosHrefs"].count("pe_tomate_extra"), 1)
        self.assertIn("pe_tomate_especial", doc["variosHrefs"])
        self.assertIn("Mín.", doc["detalhe"])
        self.assertIn("máx.", doc["detalhe"])
        self.assertIn("PR, SP, GO", doc["detalhe"])
        self.assertIn("EXTRA A", doc["detalhe"])
        self.assertIn("calculado (peso publicado)", doc["detalhe"])
        self.assertIn("firme", doc["detalhe"])
        self.assertIn("cx 20 kg", doc["detalhe"])


if __name__ == "__main__":
    unittest.main()
