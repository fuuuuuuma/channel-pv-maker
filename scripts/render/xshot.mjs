// X の投稿を公開の埋め込み表示（ログイン不要）で開き、投稿のカードだけを PNG にする。
// 使い方: node xshot.mjs <案件フォルダ> <ids.txt>（1 行に 1 つ、投稿の URL か数字の ID）
//   → assets/x/<ID>.png と research/xshot.json（取れたか・本文の頭）
import fs from 'node:fs'; import path from 'node:path';
import { chromium } from 'playwright-core';
const PROJ = path.resolve(process.argv[2]);
const OUT = path.join(PROJ, 'assets', 'x'); fs.mkdirSync(OUT, { recursive: true });
const ids = fs.readFileSync(process.argv[3], 'utf8').split('\n').map(s => (s.match(/status\/(\d+)/) || s.trim().match(/^(\d{10,})$/) || [])[1]).filter(Boolean);
const opt = {}; if (process.env.PV_CHROME) opt.executablePath = process.env.PV_CHROME; else opt.channel = 'chrome';
const browser = await chromium.launch(opt);
const page = await browser.newPage({ viewport: { width: 620, height: 1400 }, deviceScaleFactor: 3, locale: 'ja-JP' });
const res = [];
for (const id of ids) {
  if (fs.existsSync(path.join(OUT, `${id}.png`))) { res.push({ id, ok: true, cached: true }); continue; }
  try {
    await page.goto(`https://platform.twitter.com/embed/Tweet.html?id=${id}&lang=ja&theme=light&dnt=true`, { waitUntil: 'networkidle', timeout: 45000 });
    await page.waitForTimeout(1500);
    const art = await page.$('article');
    if (!art) { res.push({ id, ok: false, why: '表示されない（削除・非公開・鍵付き）' }); console.log(id, 'なし'); continue; }
    const text = (await art.innerText()).slice(0, 400);
    await art.screenshot({ path: path.join(OUT, `${id}.png`) });
    res.push({ id, ok: true, text }); console.log(id, 'ok', text.replace(/\n/g, ' ').slice(0, 80));
  } catch (e) { res.push({ id, ok: false, why: String(e).slice(0, 100) }); console.log(id, '失敗'); }
}
fs.mkdirSync(path.join(PROJ, 'research'), { recursive: true });
fs.writeFileSync(path.join(PROJ, 'research', 'xshot.json'), JSON.stringify(res, null, 1));
await browser.close();
