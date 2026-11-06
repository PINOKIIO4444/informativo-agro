#!/usr/bin/env python3
"""Publicação ENXUTA do index.html (AgroN / agronbr.com.br).

QUANDO USAR ESTE SCRIPT (só fill template→index):
  - Mudou site_template_v49.html (ou o TEMPLATE do agro_config) e quer republicar
    o HTML com os MESMOS dados embutidos do index ao vivo.
  - Exemplos recentes: XSS, feedback copy, chip/layout — sem daily, sem alertas.

QUANDO USAR daily.py (NÃO este script):
  - Precisa de dados do dia (planilha/coleta → data.json + embeds novos).
  - daily.py regenera site (index/data/alerts/assets) e pode push; use --no-push
    se só quiser gravar local. NÃO rode daily só por mudança de CSS/JS no template.
  - daily.py e o site_template devem gravar o index SEM h e rolls em cada item.
    Este fill também remove esses campos (a série fica em hist/<chave>.json).

NÃO TOCAR (este script nunca mexe):
  - og-image.png / og-image.jpg, sw.js, data.json, alerts.json, news*.json,
    hist/, CNAME (sitegit pode só garantir se já ligado), secrets/, planilha.

FLUXO:
  1) preview + OK explícito do usuário antes de --push
  2) python3 publish_index.py --dry-run          # só mostra; não grava
  3) python3 publish_index.py --tag minha_tag    # backup + grava index; SEM push
  4) python3 publish_index.py --tag X --push --msg "…"   # commit+push index (+live check)

Flags: --template, --extract-from (template que bate com o index ao vivo),
       --extra ARQ (commit extra sob site/), --skip-window-check.
Trava: usa sitegit.publish_lock no --push. Default = SEM push.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

HERE = Path(__file__).resolve().parent
SITE = HERE / "site"
BRT = ZoneInfo("America/Sao_Paulo")
PLACEHOLDER = re.compile(
    r'/\*__[A-Z]+__\*/(?:"6h"|null|true|\{\}|"")|__SITE_URL__|__RX_ORIGIN__'
)
UNTOUCHABLE = ("sw.js", "og-image.png", "og-image.jpg")


def log(msg: str) -> None:
    print(msg, flush=True)


def omit_chart_series(html: str) -> str:
    """Tira h e rolls de cada item em const DATA=.

    A série do gráfico e as trocas de contrato ficam em hist/<chave>.json.
    O restante do informativo (cotação, variação, fonte, alertas) permanece.
    """
    marker = "const DATA="
    i = html.find(marker)
    if i < 0:
        return html
    start = i + len(marker)
    if start >= len(html) or html[start] != "{":
        return html
    try:
        data, end = json.JSONDecoder().raw_decode(html, start)
    except json.JSONDecodeError:
        return html
    items = data.get("items") if isinstance(data, dict) else None
    if not isinstance(items, list):
        return html
    for it in items:
        if isinstance(it, dict):
            it.pop("h", None)
            it.pop("rolls", None)
    slim = json.dumps(data, ensure_ascii=False, separators=(",", ":"))
    return html[:start] + slim + html[end:]


def load_template_name() -> str:
    sys.path.insert(0, str(HERE))
    import agro_config as C  # noqa: WPS433
    name = getattr(C, "TEMPLATE", "site_template_v49.html")
    return str(name)


def fill(tpl: str, out: str):
    parts = PLACEHOLDER.split(tpl)
    toks = PLACEHOLDER.findall(tpl)
    vals = []
    pos = 0
    if not out.startswith(parts[0]):
        raise SystemExit(
            "index ao vivo não começa como o template de extração "
            "(passe --extract-from com o .html/.bak que gerou o index atual)"
        )
    pos = len(parts[0])
    for i, tok in enumerate(toks):
        nxt = parts[i + 1]
        key = nxt[:200] if nxt else None
        j = out.index(key, pos) if key else len(out)
        vals.append((tok, out[pos:j]))
        pos = j + len(nxt)
        if out[j : j + len(nxt)] != nxt:
            raise SystemExit(f"falha ao alinhar token {i} ({tok[:40]}…)")
    if pos != len(out):
        raise SystemExit("sobra no index após extrair tokens (template base diferente?)")
    return toks, vals


def apply(tpl: str, vals) -> str:
    m: dict[str, set[str]] = {}
    for tok, val in vals:
        m.setdefault(tok, set()).add(val)
    bad = {k: len(s) for k, s in m.items() if len(s) != 1}
    if bad:
        raise SystemExit(f"valores conflitantes por placeholder: {bad}")
    return PLACEHOLDER.sub(lambda m0: next(iter(m[m0.group(0)])), tpl)


def bak_copy(src: Path, dst: Path) -> str:
    if dst.exists():
        return f"keep {dst.name}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src, dst)
    return f"bak  {dst.name}"


def fingerprint(path: Path) -> tuple[int | None, float | None, str | None]:
    if not path.exists():
        return None, None, None
    st = path.stat()
    h = hashlib.sha256(path.read_bytes()).hexdigest()[:16]
    return st.st_size, st.st_mtime, h


def git_site(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["git", "-C", str(SITE), *args],
        check=check,
        text=True,
        capture_output=True,
    )


def summarize_diff(before: str, after: str, limit: int = 40) -> None:
    if before == after:
        log("diff: index.html INALTERADO (fill idêntico)")
        return
    import difflib

    a = before.splitlines(keepends=True)
    b = after.splitlines(keepends=True)
    hunks = list(difflib.unified_diff(a, b, fromfile="index.before", tofile="index.after", n=0))
    # só cabeçalhos @@ + poucas linhas
    shown = 0
    for line in hunks:
        if line.startswith("---") or line.startswith("+++"):
            continue
        log(line.rstrip("\n"))
        shown += 1
        if shown >= limit:
            log(f"… diff truncado ({len(hunks)} linhas no unified completo)")
            break
    log(f"diff: {len(before)} → {len(after)} bytes "
        f"(sha {hashlib.sha256(before.encode()).hexdigest()[:12]} → "
        f"{hashlib.sha256(after.encode()).hexdigest()[:12]})")


def window_check(skip: bool) -> None:
    if skip:
        return
    now = datetime.now(BRT)
    # janelas típicas das rotinas (PUBLICAR_v49): notícias :10–:25; daily ~19:15–19:45; dólar 10:10–10:45
    if 10 <= now.minute <= 25:
        raise SystemExit(
            f"janela de notícias aberta (~:{now.minute:02d} BRT). "
            "Espere ou use --skip-window-check."
        )
    if now.hour == 19 and 15 <= now.minute <= 45:
        raise SystemExit(
            "janela do daily (~19:15–19:45 BRT). Espere ou use --skip-window-check."
        )
    if now.hour == 10 and 10 <= now.minute <= 45:
        raise SystemExit(
            "janela do dólar abertura (~10:10–10:45 BRT). Espere ou use --skip-window-check."
        )


def live_check(needles: list[str]) -> None:
    import urllib.request

    url = "https://agronbr.com.br/"
    req = urllib.request.Request(url, method="GET", headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(req, timeout=30) as resp:  # noqa: S310 — URL fixa do próprio site
        body = resp.read().decode("utf-8", errors="replace")
        etag = resp.headers.get("ETag") or resp.headers.get("etag") or ""
        cf = resp.headers.get("CF-Cache-Status") or ""
        log(f"live HTTP {resp.status} ETag={etag!s} CF-Cache-Status={cf!s} len={len(body)}")
    missing = [n for n in needles if n not in body]
    if missing:
        raise SystemExit(f"live check FALHOU; ausentes: {missing}")
    log("live check OK: " + ", ".join(needles[:6]) + ("…" if len(needles) > 6 else ""))


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fill template→site/index.html sem regenerar og/sw; push só com --push."
    )
    ap.add_argument("--dry-run", action="store_true",
                    help="Não grava index, não faz backup novo obrigatório de escrita, não push.")
    ap.add_argument("--push", action="store_true",
                    help="Commit+push via sitegit (só index + extras). Exige flag explícita.")
    ap.add_argument("--tag", default="",
                    help="Sufixo dos backups (default: bak_prev_YYYYMMDD_HHMM).")
    ap.add_argument("--template", default="",
                    help="Template alvo (default: agro_config.TEMPLATE).")
    ap.add_argument("--extract-from", default="",
                    help="Template que ainda bate com o index ao vivo (default: --template).")
    ap.add_argument("--msg", default="Atualiza index.html (fill template)",
                    help="Mensagem de commit (só com --push).")
    ap.add_argument("--extra", action="append", default=[],
                    help="Arquivo extra sob site/ para incluir no commit (repetível).")
    ap.add_argument("--skip-window-check", action="store_true")
    ap.add_argument("--check-live", action="store_true",
                    help="Após --push, confere strings no https://agronbr.com.br/.")
    ap.add_argument("--needle", action="append", default=[],
                    help="String exigida no live check (default: Café, Soja, loadHist).")
    args = ap.parse_args()

    if args.push and args.dry_run:
        raise SystemExit("use --push OU --dry-run, não os dois")

    now = datetime.now(BRT)
    log(f"BRT {now.strftime('%Y-%m-%d %H:%M:%S')}")
    window_check(args.skip_window_check)

    tpl_name = args.template or load_template_name()
    tpl_path = HERE / tpl_name
    extract_path = HERE / args.extract_from if args.extract_from else tpl_path
    index_path = SITE / "index.html"
    if not tpl_path.is_file():
        raise SystemExit(f"template não encontrado: {tpl_path}")
    if not extract_path.is_file():
        raise SystemExit(f"extract-from não encontrado: {extract_path}")
    if not index_path.is_file():
        raise SystemExit(f"falta {index_path}")

    tag = args.tag or now.strftime("bak_prev_%Y%m%d_%H%M")
    log(f"tag={tag}")
    log(f"template={tpl_path.name}")
    log(f"extract-from={extract_path.name}")

    before = index_path.read_text(encoding="utf-8")
    tpl_new = tpl_path.read_text(encoding="utf-8")
    tpl_ext = extract_path.read_text(encoding="utf-8")

    toks, vals = fill(tpl_ext, before)
    rebuilt = apply(tpl_ext, vals)
    if rebuilt != before:
        raise SystemExit(
            "não reconstruí o index ao vivo a partir de --extract-from "
            "(template base diferente do que gerou o index)"
        )
    if sorted(PLACEHOLDER.findall(tpl_new)) != sorted(toks):
        raise SystemExit(
            "placeholders do template alvo ≠ tokens extraídos do index "
            f"({len(PLACEHOLDER.findall(tpl_new))} vs {len(toks)})"
        )
    after = omit_chart_series(apply(tpl_new, vals))
    if "PRIVATE" in after or "__DATA__" in after or "__SITE_URL__" in after:
        raise SystemExit("marcadores de template sobraram no HTML gerado")

    # fingerprints do que NÃO pode mudar
    fps = {name: fingerprint(SITE / name) for name in UNTOUCHABLE if (SITE / name).exists()}

    summarize_diff(before, after)
    changed = before != after
    commit_paths = ["index.html"] + list(args.extra)
    log("arquivos a commitar (se --push): " + ", ".join(commit_paths))
    if args.extra:
        for rel in args.extra:
            p = SITE / rel
            if not p.exists():
                raise SystemExit(f"--extra não existe em site/: {rel}")

    if args.dry_run:
        log("DRY-RUN: nada gravado, nenhum commit/push.")
        log(f"would_write_index={changed} bytes_out={len(after)} toks={len(toks)}")
        return 0

    # backups (estilo PUBLICAR: *.bak_<tag> na raiz do repo)
    head = git_site("rev-parse", "HEAD").stdout.strip()
    head_bak = HERE / f"site_head.{tag}"
    if not head_bak.exists():
        head_bak.write_text(head + "\n", encoding="utf-8")
        log(f"bak  {head_bak.name} = {head}")
    else:
        log(f"keep {head_bak.name}")

    log(bak_copy(index_path, HERE / f"index.html.site.{tag}"))
    if tpl_path.resolve() != extract_path.resolve() or changed:
        # backup do template alvo sempre que vamos gravar (rollback)
        log(bak_copy(tpl_path, HERE / f"{tpl_path.name}.{tag}"))
    # data/alerts snapshot opcional (não alteramos, mas facilita voltar o pacote)
    for name in ("data.json", "alerts.json"):
        src = SITE / name
        if src.exists():
            log(bak_copy(src, HERE / f"{name}.site.{tag}"))

    index_path.write_text(after, encoding="utf-8")
    log(f"wrote site/index.html ({len(after)} bytes)")

    for name, fp0 in fps.items():
        fp1 = fingerprint(SITE / name)
        if fp1 != fp0:
            raise SystemExit(f"PROTEÇÃO: {name} mudou durante o fill — abortar")
    log("ok: sw.js / og-image intactos")

    st = git_site("status", "--short", "--", "index.html", *args.extra, check=False)
    log("git status:\n" + (st.stdout.strip() or "(limpo)"))

    if not args.push:
        log("SEM --push: parei antes do commit. Rode de novo com --push após OK explícito.")
        return 0

    sys.path.insert(0, str(HERE))
    import sitegit as SG  # noqa: WPS433

    with SG.publish_lock():
        ok = SG.commit_push(commit_paths, args.msg)
    log(f"commit_push={ok}")
    head2 = git_site("rev-parse", "HEAD").stdout.strip()
    origin = git_site("rev-parse", "origin/main").stdout.strip()
    log(f"HEAD={head2}")
    log(f"origin/main={origin}")
    if head2 != origin:
        raise SystemExit("HEAD ≠ origin/main após push")
    files = [
        f for f in git_site("show", "--name-only", "--pretty=format:", "HEAD").stdout.splitlines()
        if f
    ]
    log("commit files: " + ", ".join(files))
    allowed = set(commit_paths) | {"CNAME", ".gitignore"}
    if not set(files) <= allowed:
        raise SystemExit(f"commit trouxe arquivos inesperados: {files}")
    if "index.html" not in files and changed:
        raise SystemExit("esperava index.html no commit")

    needles = args.needle or ["Café", "Soja", "Milho", "loadHist"]
    try:
        live_check(needles)
    except Exception as exc:  # noqa: BLE001
        if args.check_live:
            raise
        log(f"AVISO live check: {exc}")
        log("reconfira em alguns segundos (Pages/Cloudflare cache ~60s no HTML).")

    log(f"PUBLISH_OK {head2} {now.strftime('%H:%M')} BRT")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
