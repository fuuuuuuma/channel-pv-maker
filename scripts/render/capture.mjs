// ブラウザで描いた場面・強調テロップを 30fps で書き出す（1 コマを 4 回撮って重ね、モーションブラーにする）。
// 使い方（pv.py から呼ぶ）:
//   node capture.mjs <案件フォルダ> scenes [k1,k2]   → build/fx/<k>.mov（ProRes 422 HQ）
//   node capture.mjs <案件フォルダ> telops [k1,k2]   → build/telop/<k>.mov（ProRes 4444・透明つき）
//   node capture.mjs <案件フォルダ> still scenes|telops <k> 秒,秒  → 1 コマの PNG
// 何本かあるときは 3 枚のタブで同時に描く。/kit/ がこのフォルダ、/proj/ が案件フォルダ。
import http from 'node:http'; import fs from 'node:fs'; import path from 'node:path'; import { spawnSync } from 'node:child_process';
import { chromium } from 'playwright-core';
const KIT = path.resolve(import.meta.dirname); const PROJ = path.resolve(process.argv[2]);
const [mode, a1, a2, a3] = process.argv.slice(3);
const FF = process.env.PV_FFMPEG || 'ffmpeg';
const T = { '.html': 'text/html', '.js': 'text/javascript', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.webp': 'image/webp', '.ttf': 'font/ttf', '.json': 'application/json', '.svg': 'image/svg+xml' };
const srv = http.createServer((q, r) => {
  const u = decodeURIComponent(q.url.split('?')[0]);
  const base = u.startsWith('/proj/') ? PROJ : KIT, rel = u.replace(/^\/(proj|kit)\//, '');
  const p = path.join(base, rel);
  if (!p.startsWith(base) || !fs.existsSync(p) || fs.statSync(p).isDirectory()) { r.writeHead(404); return r.end(); }
  r.writeHead(200, { 'content-type': T[path.extname(p).toLowerCase()] || 'application/octet-stream', 'cache-control': 'no-store' }); fs.createReadStream(p).pipe(r);
});
await new Promise(r => srv.listen(0, '127.0.0.1', r));
const opt = { args: ['--force-color-profile=srgb', '--font-render-hinting=none'] };
if (process.env.PV_CHROME) opt.executablePath = process.env.PV_CHROME; else opt.channel = 'chrome';
const browser = await chromium.launch(opt);
const what = mode === 'still' ? a1 : mode;
if (mode === 'texts') {   // 字幕と名前の札を 1 枚ずつ透明な PNG に
  const pg = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  pg.on('pageerror', e => console.error('pageerror', e.message));
  await pg.goto(`http://127.0.0.1:${srv.address().port}/kit/text.html`); await pg.waitForFunction(() => window.READY === true, null, { timeout: 180000 });
  const items = JSON.parse(fs.readFileSync(path.join(PROJ, 'build', '_ff', 'texts.json'), 'utf8'));
  const od = path.join(PROJ, 'build', '_ff', 'text'); fs.mkdirSync(od, { recursive: true });
  for (let i = 0; i < items.length; i++) { await pg.evaluate(i => window.renderText(i), i); await pg.screenshot({ path: path.join(od, `${i}.png`), omitBackground: true }); }
  console.log('字幕と名前', items.length, '枚');
  await browser.close(); srv.close(); process.exit(0);
}
const page_url = `http://127.0.0.1:${srv.address().port}/kit/${what === 'telops' ? 'telop.html' : 'scenes.html'}`;
async function newPage() {
  const pg = await browser.newPage({ viewport: { width: 1920, height: 1080 } });
  pg.on('pageerror', e => console.error('pageerror', e.message));
  await pg.goto(page_url); await pg.waitForFunction(() => window.READY === true, null, { timeout: 180000 });
  return pg;
}
const transparent = what === 'telops';
// 場面のうち "overlay": true のものは透明つき（ProRes 4444）で書き出し、映像の上に重ねる
let SC = {}; try { if (!transparent) SC = JSON.parse(fs.readFileSync(path.join(PROJ, 'build', 'scenes.json'), 'utf8')).scenes || {}; } catch (e) {}
const alphaOf = k => transparent || !!(SC[k] && SC[k].overlay);
async function shot(pg, k, t, file) {
  await pg.evaluate(([k, t, tr]) => tr ? window.renderTelop(k, t) : window.renderFx(k, t), [k, t, transparent]);
  await pg.evaluate(() => Promise.all([...document.images].map(i => i.complete && i.naturalWidth ? 0 : i.decode().catch(() => 0))));
  await pg.screenshot({ path: file, omitBackground: alphaOf(k), timeout: 120000 });   // 重い場面・書き出しと重なって混む時も止めない（30 秒では時間切れになった）
}
const outDir = path.join(PROJ, 'build', transparent ? 'telop' : 'fx'); fs.mkdirSync(outDir, { recursive: true });
let durs = {};
if (transparent) { const J = JSON.parse(fs.readFileSync(path.join(PROJ, 'build', 'telops.json'), 'utf8')); for (const k in J) durs[k] = J[k].dur; }
else { const TL = JSON.parse(fs.readFileSync(path.join(PROJ, 'build', 'timeline.json'), 'utf8')); for (const b of TL.blocks) if (b.t === 'fx' && !b.kind) durs[b.k] = b.dur; }
if (mode === 'still') {
  const pg = await newPage();
  for (const t of a3.split(',').map(Number)) { const f = path.join(outDir, `_still_${a2}_${t}.png`); await shot(pg, a2, t, f); console.log(f); }
} else {
  const want = (a1 ? a1.split(',').filter(Boolean) : []).length ? a1.split(',') : Object.keys(durs);
  // 1 コマを何回撮って重ねるか（動きのぼかし）。既定 4。止まった文字や額だけの場面は scenes.json の "mblur": 1 で 4 倍速く書ける。PV_SUBFRAMES・PV_TABS で全体を替える
  const K0 = Number(process.env.PV_SUBFRAMES || 4), fps = 30, queue = want.filter(k => { if (!(k in durs)) console.error('無い:', k); return k in durs; });
  // 長い場面は 150 コマ（5 秒）ずつに分けて、空いているタブで同時に描く。全部そろった場面から ProRes にまとめる
  const CH = 150, left = {}, tasks = [];
  for (const k of queue) {
    const N = Math.round(durs[k] * fps), K = Math.max(1, Number((SC[k] && SC[k].mblur) || K0)), dir = path.join(outDir, `_${k}`);
    fs.rmSync(dir, { recursive: true, force: true }); fs.mkdirSync(dir);
    left[k] = Math.ceil(N / CH);
    for (let a = 0; a < N; a += CH) tasks.push({ k, N, K, dir, a, b: Math.min(N, a + CH) });
  }
  tasks.sort((x, y) => y.N - x.N || x.a - y.a);                // 長い場面から先に（最後に 1 枚だけ残って待つのを防ぐ）
  function encode(k, N, K, dir) {
    const al = alphaOf(k);
    const vf = `${al ? 'format=rgba,' : ''}tmix=frames=${K},select='eq(mod(n\\,${K})\\,${K - 1})',setpts=N/${fps}/TB`;
    const enc = al ? ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le'] : ['-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le'];
    const r = spawnSync(FF, ['-v', 'error', '-y', '-framerate', String(fps * K), '-i', path.join(dir, 's_%05d.png'), '-vf', vf, '-r', String(fps), ...enc, path.join(outDir, `${k}.mov`)]);
    if (r.status !== 0) console.error(k, String(r.stderr || r.error)); else fs.rmSync(dir, { recursive: true, force: true });
    const pr = spawnSync(FF.replace(/ffmpeg$/, 'ffprobe'), ['-v', 'error', '-count_packets', '-select_streams', 'v:0', '-show_entries', 'stream=nb_read_packets', '-of', 'csv=p=0', path.join(outDir, `${k}.mov`)]);
    const got = parseInt(String(pr.stdout || '').trim(), 10);
    if (got !== N) { console.error(`!! ${k} の書き出しが ${got} コマで切れた（必要 ${N} コマ）`); process.exitCode = 1; }   // 途中で切れたら止める（前は黙って短い動画になった）
    console.log(k, N, 'コマ →', path.join(outDir, `${k}.mov`));
  }
  async function worker() {
    const pg = await newPage();
    while (tasks.length) {
      const { k, N, K, dir, a, b } = tasks.shift();
      for (let i = a; i < b; i++) for (let s = 0; s < K; s++) await shot(pg, k, i / fps + s * (0.5 / fps) / K, path.join(dir, `s_${String(i * K + s).padStart(5, '0')}.png`));
      if (--left[k] === 0) encode(k, N, K, dir);
    }
  }
  await Promise.all(Array.from({ length: Math.min(Number(process.env.PV_TABS || 3), tasks.length) }, worker));
}
await browser.close(); srv.close();
