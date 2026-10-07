"""ブラウザで描くもの（場面・強調テロップ）の書き出しと、強調の縦書きの置き方。
  pv.py scenes [k,...]          build/scenes.json の場面 → build/fx/<k>.mov（ProRes 422・モーションブラー）
  pv.py telops [k,...]          edl.py の big → build/telops.json → build/telop/<k>.mov（ProRes 4444・透明つき）
  pv.py still scenes|telops k 秒,秒   1 コマだけ PNG（build/fx/_still_* / build/telop/_still_*）で確かめる
"""
import json, subprocess
from . import env

ACCENT = ('pink', 'red', 'ybox')


def _cols(big):
    if isinstance(big, str):
        ls = [l for l in big.split('\n') if l.strip()]
        return [[l, 'pink' if i == len(ls) - 1 and len(ls) > 1 else 'white'] for i, l in enumerate(ls)]
    return [[c[0], c[1] if len(c) > 1 else 'white'] for c in big]


def layout(big):
    """縦書きの列を、読む順（右から）に「右の端の列」→「左の端の列」へ置く。効かせる語（pink/red/ybox）は左の端に大きく"""
    cols = _cols(big)
    right = [c for c in cols if c[1] not in ACCENT]; left = [c for c in cols if c[1] in ACCENT]
    if not left and len(right) > 1: left = [right.pop()]
    if not right and len(left) > 1: right = [left.pop(0)]
    out = []
    rs = [max(110, min(230, int(1000 / max(1, len(t))))) for t, _ in right]
    while sum(rs) + 12 * (len(rs) - 1) > 560: rs = [int(s * .9) for s in rs]
    x = 1920 - 34
    for i, ((t, st), s) in enumerate(zip(right, rs)):
        x -= s; out.append(dict(text=t, style=st, size=s, x=x, y=40 + 70 * i, **{'from': 'R'}, at=round(.16 * i, 2))); x -= 12
    ls = [max(130, min(330 if st in ACCENT else 200, int(1000 / max(1, len(t))))) for t, st in left]
    while sum(ls) + 12 * (len(ls) - 1) > 620: ls = [int(s * .9) for s in ls]
    x = 34 + sum(ls) + 12 * (len(ls) - 1)
    for i, ((t, st), s) in enumerate(zip(left, ls)):
        x -= s; out.append(dict(text=t, style=st, size=s, x=x, y=30 + 100 * i, **{'from': 'L'}, at=round(.16 * len(right) + .1 + .15 * i, 2))); x -= 12
    for c in out:                                   # 下にはみ出さないように
        c['size'] = min(c['size'], int((1050 - c['y']) / max(1, len(c['text']))))
    return out


def telops_json(P):
    comp = P.jload('_comp.json')
    blocks = P.blocks(); out = {}
    for b in comp['bigs']:
        o = blocks[b['k']]
        cols = o.get('layout') or layout(o['big'])
        for c in cols:
            if 'from_' in c: c['from'] = c.pop('from_')
        out[b['k']] = dict(dur=round(b['end'] - b['t'], 3), cols=cols)
    P.jsave('telops.json', out)
    return out


def _node(P, mode, args):
    if not env.node(): raise SystemExit('node がありません（https://nodejs.org）')
    if not env.playwright_ready():
        print('playwright-core を入れます（初回だけ）'); subprocess.run(['npm', 'install', '--silent'], cwd=env.RENDER, check=True)
    tex = env.RENDER / 'tex' / 'grunge_pink.png'
    if mode.startswith('telop') or 'telops' in args:
        if not tex.exists():
            from .textures import make; make(env.RENDER / 'tex')
    cmd = [env.node(), str(env.RENDER / 'capture.mjs'), str(P.root), *args]
    e = dict(**__import__('os').environ, PV_FFMPEG=env.ffmpeg())
    c = env.chrome()
    if c: e['PV_CHROME'] = c
    subprocess.run(cmd, check=True, env=e)


def scenes(P, keys=None):
    _node(P, 'scenes', ['scenes', ','.join(keys) if keys else ''])


def telops(P, keys=None):
    telops_json(P)
    _node(P, 'telops', ['telops', ','.join(keys) if keys else ''])


def still(P, what, k, times):
    if what == 'telops': telops_json(P)
    _node(P, what, ['still', what, k, times])
