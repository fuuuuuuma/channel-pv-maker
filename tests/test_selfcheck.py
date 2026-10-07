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


for p in [S / 'pv.py', *sorted((S / 'pvkit').glob('*.py')), S / 'templates' / 'edl.py']:
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
for ref in ('interview', 'structure', 'pipeline', 'design', 'rules', 'qa', 'extras', 'gotchas'):
    check(f'references/{ref}.md がある', (R / 'skills' / 'channel-pv' / 'references' / f'{ref}.md').exists())
with tempfile.TemporaryDirectory() as d:
    r = subprocess.run([sys.executable, str(S / 'pv.py'), 'init', d + '/p', '--name', 't'], capture_output=True, text=True)
    check('init', r.returncode == 0 and (Path(d) / 'p' / 'pv.project.json').exists())
    r = subprocess.run([sys.executable, 'edl.py'], cwd=Path(d) / 'p' / 'build', capture_output=True, text=True)
    tl = json.load(open(Path(d) / 'p' / 'build' / 'timeline.json'))
    check('設計図の雛形が時刻表を書く', r.returncode == 0 and tl['total'] > 10 and tl['pics'])
from pvkit.render import layout
cols = layout([('仲間がいて', 'white'), ('初めて', 'white'), ('幸せに', 'pink'), ('なれる', 'white')])
check('強調：効かせる語は左の端', [c for c in cols if c['text'] == '幸せに'][0]['x'] < 400)
check('強調：白の列は右の端', all(c['x'] > 1300 for c in cols if c['from'] == 'R'))
check('強調：下にはみ出さない', all(c['y'] + c['size'] * len(c['text']) <= 1060 for c in cols))
from pvkit.plan import chunk_times
ts = chunk_times([[0, .5, 'こんにちは'], [.6, 1.0, '今日は'], [1.1, 1.6, 'いい天気']], ['こんにちは', '今日は いい天気'])
check('字幕の切り替え時刻', ts[0] == 0 and .5 < ts[1] < .7)
print(f'\n{ok} 項目 すべて OK')
