// Captura quadro a quadro, em tempo virtual determinístico (HeadlessExperimental.beginFrame)
// uso: node capture.js <saida> [modo: video|shots] [inicioMs] [fimMs] [passo]
const { chromium } = require('playwright');
const { spawn } = require('child_process');
const fs = require('fs');
const S = __dirname;
const [,, OUT, MODE = 'video', A = '0', B = '999999', STEP = '1'] = process.argv;
const FPS = 30, DT = 1000 / FPS;

(async () => {
  const browser = await chromium.launch({
    executablePath: '/opt/pw-browsers/chromium_headless_shell-1194/chrome-linux/headless_shell',
    args: ['--deterministic-mode', '--enable-begin-frame-control', '--disable-new-content-rendering-timeout',
      '--run-all-compositor-stages-before-draw', '--disable-threaded-animation', '--disable-threaded-scrolling',
      '--disable-checker-imaging', '--disable-image-animation-resync',
      '--enable-unsafe-swiftshader', '--use-angle=swiftshader', '--ignore-gpu-blocklist', '--enable-webgl',
      '--font-render-hinting=none', '--disable-site-isolation-trials']
  });
  const ctx = await browser.newContext({ viewport: { width: 1080, height: 1920 }, deviceScaleFactor: 1, ignoreHTTPSErrors: true });
  await ctx.route('**/cdnjs.cloudflare.com/**', r => r.fulfill({ path: S + '/three.min.js', contentType: 'application/javascript' }));
  const page = await ctx.newPage();
  page.on('pageerror', e => console.log('PAGEERR', e.message));
  page.on('console', m => { if (m.type() === 'error') console.log('CONSOLE', m.text()); });
  const cdp = await ctx.newCDPSession(page);
  await cdp.send('Emulation.setVirtualTimePolicy', { policy: 'pause' });
  page.goto('http://localhost:8090/stage.html').catch(() => {});

  const T0 = Number(process.hrtime.bigint() / 1000000n) + 1000;
  let tick = 0;
  async function frame(shot) {
    await cdp.send('Emulation.setVirtualTimePolicy', { policy: 'pauseIfNetworkFetchesPending', budget: DT });
    await new Promise(r => cdp.once('Emulation.virtualTimeBudgetExpired', r));
    tick += DT;
    const args = { frameTimeTicks: T0 + tick, interval: DT, noDisplayUpdates: false };
    if (shot) args.screenshot = { format: 'png' };
    const r = await cdp.send('HeadlessExperimental.beginFrame', args);
    return r.screenshotData ? Buffer.from(r.screenshotData, 'base64') : null;
  }
  const ev = async e => (await cdp.send('Runtime.evaluate', { expression: e, returnByValue: true })).result.value;

  // aquecimento: carrega tudo até a página dizer que está pronta
  let n = 0;
  while (true) {
    await frame(false); n++;
    if (n % 10 === 0 && await ev('window.__ready === true').catch(() => false)) break;
    if (n > 3000) throw new Error('não ficou pronto');
  }
  for (let i = 0; i < 45; i++) await frame(false);
  console.log('pronto após', n, 'quadros');
  await ev('window.start(); 1');

  let ff = null, last = null;
  if (MODE === 'video') {
    ff = spawn('ffmpeg', ['-v', 'error', '-y', '-f', 'image2pipe', '-framerate', String(FPS), '-c:v', 'png', '-i', '-',
      '-c:v', 'libx264', '-preset', 'medium', '-crf', '17', '-pix_fmt', 'yuv420p', '-movflags', '+faststart', OUT], { stdio: ['pipe', 'inherit', 'inherit'] });
  } else fs.mkdirSync(OUT, { recursive: true });

  const t1 = Date.now();
  for (let i = 0; ; i++) {
    const tms = i * DT;
    const want = tms >= +A && tms <= +B && (i % +STEP === 0);
    const img = await frame(want);
    if (want) {
      const buf = img || last;
      if (buf) {
        last = buf;
        if (ff) { if (!ff.stdin.write(buf)) await new Promise(r => ff.stdin.once('drain', r)); }
        else fs.writeFileSync(`${OUT}/f${String(Math.round(tms)).padStart(6, '0')}.png`, buf);
      }
    }
    if (i % 300 === 0) console.log('t=', (tms / 1000).toFixed(1), 's  real', ((Date.now() - t1) / 1000).toFixed(0), 's');
    if (tms > +B) break;
    if (i % 15 === 0 && await ev('window.__done === true')) break;
  }
  fs.writeFileSync(S + '/events.json', JSON.stringify(await ev('window.__events')));
  if (ff) { ff.stdin.end(); await new Promise(r => ff.on('close', r)); }
  await browser.close();
  console.log('fim');
})().catch(e => { console.error(e); process.exit(1); });
