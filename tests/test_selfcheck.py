"""外部の道具を使わずにできる点検：構文・雛形の JSON・設計図の雛形が動くか・強調の置き方。
使い方: python3 tests/test_selfcheck.py"""
import json, py_compile, shutil, subprocess, sys, tempfile
from pathlib import Path

R = Path(__file__).resolve().parent.parent
S = R / 'scripts'
sys.path.insert(0, str(S))
ok = 0


def check(name, cond):
    global ok
    print(('OK  ' if cond else 'NG  ') + name)
    if not cond: raise SystemExit(1)
    ok += 1


for p in [S / 'pv.py', S / 'look.py', *sorted((S / 'pvkit').glob('*.py')), S / 'templates' / 'edl.py']:
    py_compile.compile(str(p), doraise=True)
check('Python の構文', True)
for f in ('style.json', 'scenes.json', 'audio.json', 'framing.json', 'montage_pick.json'):
    json.load(open(S / 'templates' / f))
check('雛形の JSON', True)
for f in ('marketplace.json', 'plugin.json'):
    json.load(open(R / '.claude-plugin' / f))
check('プラグインの定義', True)
skill = (R / 'skills' / 'channel-pv' / 'SKILL.md').read_text()
check('SKILL.md の頭書き', skill.startswith('---\nname: channel-pv\ndescription: '))
for ref in ('interview', 'structure', 'pipeline', 'design', 'rules', 'qa', 'review', 'directing', 'extras', 'gotchas', 'motion', 'trailer', 'wedding'):
    check(f'references/{ref}.md がある', (R / 'skills' / 'channel-pv' / 'references' / f'{ref}.md').exists())
with tempfile.TemporaryDirectory() as d:
    r = subprocess.run([sys.executable, str(S / 'pv.py'), 'init', d + '/p', '--name', 't'], capture_output=True, text=True)
    check('init', r.returncode == 0 and (Path(d) / 'p' / 'pv.project.json').exists())
    r = subprocess.run([sys.executable, 'edl.py'], cwd=Path(d) / 'p' / 'build', capture_output=True, text=True)
    tl = json.load(open(Path(d) / 'p' / 'build' / 'timeline.json'))
    check('設計図の雛形が時刻表を書く', r.returncode == 0 and tl['total'] > 10 and tl['pics'])
    e = Path(d) / 'p' / 'build' / 'edl.py'; src = e.read_text()                 # 素材の映像と重ねる場面（結婚式ムービーの組み方）
    body = "ai('a', 'x.mp4', 5.0, src=2.0, zoom=(1.0, 1.04), box=[0, 0, 960, 540])\nover('c', 4.0, at=.5)\nai('b', 'y.mp4', 4.0, gap=-.5, fade=.5)\nfx('end', 3.0)\n"
    import re as _re
    e.write_text(_re.sub(r'(# ===== ここから[^\n]*\n).*?(# ===== ここまで)', lambda m: m.group(1) + body + m.group(2), src, flags=_re.S))
    r = subprocess.run([sys.executable, 'edl.py'], cwd=Path(d) / 'p' / 'build', capture_output=True, text=True)
    bl = {b['k']: b for b in json.load(open(Path(d) / 'p' / 'build' / 'timeline.json'))['blocks']}
    check('over は直前の映像に重なり時間を進めない', r.returncode == 0 and bl['c']['T'] == .5 and bl['b']['T'] == 4.5 and bl['end']['T'] == 8.5)
    check('ai の使い始め・寄り・枠・溶け', bl['a']['src'] == 2.0 and bl['a']['box'] == [0, 0, 960, 540] and bl['b']['fade'] == .5)
import math
from pvkit import mapdata
ring = [(math.cos(a / 40 * 2 * math.pi) * 100, math.sin(a / 40 * 2 * math.pi) * 100) for a in range(40)]; ring.append(ring[0])
far = max(range(len(ring)), key=lambda i: math.hypot(ring[i][0] - ring[0][0], ring[i][1] - ring[0][1]))
check('地図：閉じた輪郭がつぶれない', len(mapdata._simplify(ring[:far + 1], 1.2)[:-1] + mapdata._simplify(ring[far:], 1.2)) > 8)
html = (S / 'render' / 'scenes.html').read_text()
check('場面の種類：card / photo / credits / countdown', all(f'S.{t} = function' in html for t in ('card', 'photo', 'credits', 'countdown')))
check('card の pos に左右のそろえ', "pos[2] === 'left'" in html)
check('上位の部品：glow / leak / page / stack・止まった地・白黒→カラー', all(f'S.{t} = function' in html for t in ('glow', 'leak', 'page', 'stack'))
      and 'function back(c)' in html and 'grayscale(${mono})' in html and 'age_big' in html)
check('山場で黒帯を開く（AE と ffmpeg）・昔の写真の色・ページの切り取る位置・注記の右寄せ', 'letterbox_open' in (S / 'ae' / 'build_body.jsx').read_text()
      and 'letterbox_open' in (S / 'pvkit' / 'compose.py').read_text() and 'letterbox_open' in (S / 'pvkit' / 'plan.py').read_text()
      and all(k in html for k in ('c.aged', '(c.focus || [])[i]', 'c.foot_w')) and html.count('${-dx * .5}') == 1)
check('写真は止めない（push・drift）・重なる写真の置き場所と暗転・注記の左寄せ', all(k in html for k in ('c.drift', 'c.spots', 'c.dark_out', 'c.foot_x', 'c.label_at')))
check('幕（glow の fade_in 0）は 1 コマ目から黒・書き出しの音は aac_at を優先', 'fi > 0 ? P(t, 0, fi) : 1' in html
      and all("env.aac()" in (S / 'pvkit' / f).read_text() for f in ('ae.py', 'compose.py')))
check('透明の場面は左上の 1 点を透明に・書き出しのコマ数を点検', "polygon(1px 0,100% 0" in html and 'で切れた' in (S / 'render' / 'capture.mjs').read_text())
check('文字の形に映像を抜く（AE と ffmpeg）', 'setTrackMatte(ml' in (S / 'ae' / 'build_body.jsx').read_text() and 'alphamerge' in (S / 'pvkit' / 'compose.py').read_text()
      and "matte=matte" in (S / 'templates' / 'edl.py').read_text())
import tempfile
from pvkit import texture
with tempfile.TemporaryDirectory() as td:
    texture.make('paper', '#efe7da', f'{td}/p.png')
    from PIL import Image
    im = Image.open(f'{td}/p.png'); px = [im.getpixel((x, 540))[0] for x in range(0, 1920, 97)]
    check('地の PNG：1920×1080・むらがある', im.size == (1920, 1080) and max(px) - min(px) >= 3)
mixsrc = (S / 'pvkit' / 'mix.py').read_text()
check('音の時刻：足し引きを何段でも（hand.T+4.4+0.3）', r'((?:\s*[+-]\s*[\d.]+)*)' in mixsrc)
check('書き出しの前に音が今の版か点検', all('check_mix(' in (S / 'pvkit' / f).read_text() for f in ('ae.py', 'compose.py')))
import look
check('見る道具：読み切れない文字', [b['text'] for b in look.read_check([dict(text='見つけ次第即退出', start=0, end=.4), dict(text='はい', start=1, end=1.6, voice=True)])] == ['見つけ次第即退出'])
from pvkit.render import layout
cols = layout([('仲間がいて', 'white'), ('初めて', 'white'), ('幸せに', 'pink'), ('なれる', 'white')])
check('強調：効かせる語は左の端', [c for c in cols if c['text'] == '幸せに'][0]['x'] < 400)
check('強調：白の列は右の端', all(c['x'] > 1300 for c in cols if c['from'] == 'R'))
check('強調：下にはみ出さない', all(c['y'] + c['size'] * len(c['text']) <= 1060 for c in cols))
from pvkit.plan import chunk_times
ts = chunk_times([[0, .5, 'こんにちは'], [.6, 1.0, '今日は'], [1.1, 1.6, 'いい天気']], ['こんにちは', '今日は いい天気'])
check('字幕の切り替え時刻', ts[0] == 0 and .5 < ts[1] < .7)
MP = R / 'skills' / 'channel-pv' / 'references' / 'motion-prompt'
from pvkit import motion
check('動きの名前：一覧が 168 件', len(motion.load()) == 168)
check('動きの名前：頼み方が 168 件', len(list((MP / 'prompts').glob('*.txt'))) == 168)
check('動きの名前：MIT の表示を同梱', 'Shohei Ohtaki' in (MP / 'LICENSE').read_text())
check('動きの名前：「ゆっくり寄る」→ #027 ドリーイン', motion.search(['ゆっくり寄る'])[0]['id'] == '027')
check('動きの名前：「横に流す」→ #025 パン', motion.search(['横に流す'])[0]['id'] == '025')
check('動きの名前：「ポンと出して」→ #001 ポップイン', motion.search(['ポンと出して'])[0]['id'] == '001')
check('動きの名前：番号で頼み方', 'Motion Prompt #044' in motion.prompt('44'))
r = subprocess.run([sys.executable, str(S / 'pv.py'), 'motion', 'ふわふわ'], capture_output=True, text=True)
check('pv.py motion が案件フォルダの外で動く', r.returncode == 0 and '#096' in r.stdout)
ids = set()
for v in motion.ALIAS.values():
    ids |= set(v)
known = {r['id'] for r in motion.load()}
check('早見の番号がすべて一覧にある', ids <= known)
print(f'\n{ok} 項目 すべて OK')
