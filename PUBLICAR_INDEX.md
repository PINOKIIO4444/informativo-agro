# publish_index.py — publicação enxuta do index

- **Só fill:** `site_template_*.html` → `site/index.html` com os embeds do index ao vivo. O fill omite `h` (série do gráfico) e `rolls` (trocas de contrato) de cada item em `const DATA=`. Esses dados ficam em `hist/<chave>.json`. O restante do informativo continua no HTML. `daily.py` e o `site_template` devem emitir o index já sem esses campos.
- **daily.py:** use quando precisar dos dados do dia (coleta/planilha). Não rode daily por CSS/JS.
- **news_publish.py:** só notícias (`news_v2.json` etc.), independente deste script.
- **Nunca toca:** `og-image.png`/`og-image.jpg`, `sw.js`, `data.json`, `alerts.json`, `hist/`, secrets.
- **Default:** grava local + backup `*.{tag}`; **não** faz push.
- **Dry-run:** `python3 publish_index.py --dry-run` (não grava).
- **Push:** só com `--push` e OK explícito; usa `sitegit` (trava + pull --rebase).
- Se editou o template e o index ao vivo ainda é o antigo: `--extract-from site_template_v49.html.bak_…`.
- Evite janelas :10–:25 (notícias), 19:15–19:45 (daily), 10:10–10:45 (dólar) ou `--skip-window-check`.
- Cloudflare na frente não muda o publish (continua GitHub Pages / repo `site/`).
