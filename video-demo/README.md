# Vídeo de demonstração do site

`fondly-demo.mp4` é o vídeo vertical (1080×1920, 30 fps, cerca de 1min29) que mostra
o site funcionando: montagem com prévia, caneca 3D, foto e frase aplicadas na hora,
pedido indo pro WhatsApp, catálogo, portfólio, dúvidas, e o layout se ajustando no
celular, no tablet e no computador.

Nada aqui é encenado por fora: o vídeo abre o `index.html` de verdade dentro dos
aparelhos e clica, digita e arrasta nele. A única parte simulada é a tela do WhatsApp,
que mostra a mensagem que o site gerou de fato.

## Como gerar de novo

Precisa de Node com Playwright, do Chromium headless shell, de ffmpeg e de Python
com numpy e scipy.

```bash
mkdir -p www && cp stage.html fonts.css www/ && cp -r fonts www/
ln -s "$(pwd)/.." www/site
cp ../img-png-1-71768d12b0ce.png www/logo.png
npx http-server www -p 8090 -s &
# three.min.js (r128) ao lado do capture.js: npm pack three@0.128.0
node capture.js video_silent.mp4 video      # grava quadro a quadro e gera events.json
python3 audio.py 89 events.json          # trilha + efeitos sincronizados → audio.wav
ffmpeg -i video_silent.mp4 -i audio.wav -c:v libx264 -crf 20 -preset slow \
  -pix_fmt yuv420p -c:a aac -b:a 160k -shortest -movflags +faststart fondly-demo.mp4
```

- `stage.html`: o palco do vídeo, com legendas, aparelhos, dedo e roteiro (`window.start`).
- `capture.js`: grava em tempo virtual determinístico (`HeadlessExperimental.beginFrame`),
  então cada animação sai lisa, sem pulo de quadro.
- `audio.py`: trilha lo-fi sintetizada e sons de toque, digitação e transição nos
  instantes registrados em `events.json`.

A pasta fica fora do deploy da Vercel (`.vercelignore`).
