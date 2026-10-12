#!/usr/bin/env bash
# Génère la version web (servie sur https://lantantetechnologie.com/app/) dans ../LucasTech/webapp, installable sur l'écran d'accueil.
set -e
cd "$(dirname "$0")/.."
OUT="../LucasTech/webapp"
rm -rf "$OUT"
CI=1 npx expo export --platform web --output-dir "$OUT"
python - "$OUT/index.html" <<'PY'
import sys
p = sys.argv[1]
s = open(p, encoding='utf-8').read()
s = s.replace('<html lang="en">', '<html lang="fr">')
tags = ('<link rel="manifest" href="/app/manifest.webmanifest">'
        '<link rel="apple-touch-icon" href="/app/icon-192.png">'
        '<meta name="apple-mobile-web-app-capable" content="yes">'
        '<meta name="mobile-web-app-capable" content="yes">'
        '<meta name="apple-mobile-web-app-title" content="LT Job">'
        '<meta name="description" content="Offres d\'emploi, stages et recrutement au Togo et en Afrique.">')
tags += ('<script>window.addEventListener("beforeinstallprompt",function(e){e.preventDefault();window.__installPrompt=e;'
         'window.dispatchEvent(new Event("installready"))});'
         'if("serviceWorker" in navigator){window.addEventListener("load",function(){navigator.serviceWorker.register("/app/sw.js",{scope:"/app/"})})}</script>')
s = s.replace('</head>', tags + '</head>', 1)
open(p, 'w', encoding='utf-8').write(s)
PY
echo "Version web générée dans $OUT"
