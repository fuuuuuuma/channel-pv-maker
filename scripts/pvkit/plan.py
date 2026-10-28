"""timeline.json から「組み立ての中身」build/_comp.json を作る（AE でも ffmpeg でも同じものを読む）。
- 絵：framing.json の倍率・位置。切り替えはディゾルブ。ただし素材の直前に元動画の編集点があれば溶かす長さを縮め、足りなければ切る
- 暗転（dip）の手前の絵は黒へ溶けて消える。黒い場面の後に間があれば黒から短く溶けて入る
- 強調：縦書きのテロップ（build/telop/<k>.mov）と、その瞬間に話者の顔へ寄る（punch）
- 字幕：edl.py の区切りを、transcripts.json の語の時刻に合わせて切り替える
"""
import difflib, json, subprocess, unicodedata
import numpy as np
from . import env
from .checks import detect


def edit_before(path, off, look, fps):
    """素材の off 秒の直前 look 秒にある編集点（新しいカットの最初のコマの時刻）。無ければ None"""
    a = max(0, off - look)
    raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-ss', f'{a:.3f}', '-i', str(path), '-t', f'{off - a + 2 / fps:.3f}', '-vf', 'scale=96:54,format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.uint8).reshape(-1, 54, 96).astype(np.float32)
    if len(x) < 4: return None
    d = np.abs(np.diff(x, axis=0)).mean((1, 2)); med = np.median(d) + .5
    c = [a + (i + 1) / fps for i in range(len(d)) if d[i] > 11 and d[i] > 6 * med]
    c = [t for t in c if t <= off + .5 / fps]
    return max(c) if c else None


def norm(s):
    s = unicodedata.normalize('NFKC', s).upper()
    return ''.join(ch for ch in s if ch not in ' 　「」『』？！?!〜~ー・、。,.…"\'')


def chunk_times(words, chunks):
    """各区切りが話され始める時刻（声の始まりからの秒）。語の時刻と文字を突き合わせ、合わない所は文字数の割合で"""
    raw, tm = '', []
    for s0, s1, w in words:
        w = norm(w)
        for j, ch in enumerate(w): raw += ch; tm.append(s0 + (s1 - s0) * j / max(1, len(w)))
    joined, starts = '', []
    for c in chunks: starts.append(len(joined)); joined += norm(c)
    pairs = []
    if raw and joined:
        sm = difflib.SequenceMatcher(None, joined, raw, autojunk=False)
        pairs = [(m.a + i, m.b + i) for m in sm.get_matching_blocks() for i in range(m.size)]
    end = words[-1][1] if words else None
    out = []
    for st in starts:
        if st == 0: out.append(0.); continue
        cand = [bj for ai, bj in pairs if ai >= st]
        out.append(tm[cand[0]] if cand and cand[0] < len(tm) else (None if end is None else end * st / max(1, len(joined))))
    return out


def build(P):
    S = P.style(); fps = S['fps']; F = 1 / fps
    TL = P.tl; pics = TL['pics']; BL = P.blocks()
    TR = P.jload('transcripts.json', {})
    keymap = {id(p): k for k, p in P.shots()}
    items, shortened = [], []
    for i, p in enumerate(pics):
        if 'fxk' in p: continue
        key = keymap[id(p)]
        s, y, x = P.framing(key, p)
        f, off = P.source(p, pre=.3, post=.3)
        prv = pics[i - 1] if i > 0 else None
        it = dict(t0=p['t0'], t1=p['t1'], blk=p['blk'], key=key, file=str(f), off=round(off, 3), scale=round(s * 100, 2),
                  anchor=[960 + x, 540 + y], look=p.get('look', ''), sync=p['sync'], fin=0., pre=0., fout=0.)
        if prv is None: it['fin'] = .6
        elif 'fxk' in prv or p.get('hard') or p.get('look') == 'cut':
            if 'fxk' in prv and p['t0'] > prv['t1'] + F / 2: it['fin'] = .25        # 黒い場面の後に間があるときは黒から短く溶けて入る
        else:
            d = (6 if prv['blk'] == p['blk'] else (12 if p['dip'] else 8)) * F
            e = edit_before(f, off, d + .1, fps)
            if e is not None and e > off - d - F / 2:                              # 溶かすと前の別カットが混ざる → 縮める／切る
                d = max(0., round((off - e) * fps) / fps); shortened.append((key, round(d * fps)))
                if d < 2 * F: d = 0.
            it['fin'] = it['pre'] = round(d, 3)
        nxt = pics[i + 1] if i + 1 < len(pics) else None
        if nxt is not None and nxt.get('dip') and nxt['t0'] > p['t1'] + F / 2:   # 暗転の手前は黒へ溶けて消える
            it['fout'] = round(min(.27, (p['t1'] - p['t0']) / 3), 3)
        items.append(it)

    blk_end = {}
    for p in pics: blk_end[p['blk']] = max(blk_end.get(p['blk'], 0), p['t1'])

    fxl = []
    SC = P.jload('scenes.json', {}).get('scenes', {})
    mattes = {o['matte'] for o in TL['blocks'] if o.get('matte')}       # 文字の形に映像を抜く場面（それ自体は重ねない）
    for n, o in enumerate(TL['blocks']):
        if o['t'] != 'fx' or o.get('kind') == 'montage': continue
        nxt = TL['blocks'][n + 1] if n + 1 < len(TL['blocks']) else None
        ai = o.get('kind') == 'ai'
        f = (P.root / o['file']) if ai else (P.build / 'fx' / f"{o['k']}.mov")
        x = dict(k=o['k'], t0=o['T'], t1=o['end'], file=str(f), ai=ai,
                 fout=.3 if nxt and nxt['t'] == 'line' and not nxt.get('dip') and not ai else 0)
        if ai: x.update(src=o.get('src') or 0., zoom=o.get('zoom'), box=o.get('box'), shift=o.get('shift'), fade=o.get('fade') or 0., fout=o.get('fout') or 0.)
        if ai and o.get('matte'): x['matte'] = str(P.build / 'fx' / f"{o['matte']}.mov")
        if not ai and o['k'] in mattes: x['matte_only'] = True
        if not ai and SC.get(o['k'], {}).get('blend'): x['blend'] = SC[o['k']]['blend']     # screen / add：光漏れ・光の粒を明るく重ねる
        fxl.append(x)

    punches, bigs = [], []
    tmp = P.build / '_chk'; tmp.mkdir(exist_ok=True)
    for o in TL['blocks']:
        if not o.get('big') or o.get('bigt') is None: continue
        v = o['voice']; t = v['t0'] + o['bigt']
        end = v['t0'] + o['bige'] if o.get('bige') else blk_end.get(o['k'], o['end'])
        bigs.append(dict(k=o['k'], t=round(t, 3), end=round(end, 3), file=str(P.build / 'telop' / f"{o['k']}.mov")))
        if not o.get('punch'): continue
        cfg = o['punch'] if isinstance(o['punch'], dict) else {}
        z, land = cfg.get('z', 1.25), cfg.get('land', [960, 520])
        tp = t - .12
        idx = next((i for i, it in enumerate(items) if it['t0'] - it['pre'] <= tp < it['t1']), None)
        if idx is None: print('寄る絵が無い', o['k']); continue
        it = items[idx]; s0 = it['scale']; s1 = s0 * z
        img = tmp / f"punch_{o['k']}.png"
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-ss', f"{it['off'] + (tp + .05 - it['t0']):.3f}", '-i', it['file'], '-frames:v', '1', str(img)], check=True)
        fs = [f for f in (detect([img])[0] or []) if f[3] - f[1] >= 60]
        if fs:
            pick = cfg.get('face', 'largest')                     # 寄る顔：largest（一番大きい）/ left / right / center
            key_ = {'left': lambda b: b[0], 'right': lambda b: -b[2], 'center': lambda b: abs((b[0] + b[2]) / 2 - it['anchor'][0])}.get(pick)
            f = min(fs, key=key_) if key_ else max(fs, key=lambda b: (b[2] - b[0]) * (b[3] - b[1])); fc = [(f[0] + f[2]) / 2, (f[1] + f[3]) / 2]
        else:
            print('寄りの先に顔が見つからないので画面の中心へ寄る', o['k']); fc = it['anchor']
        a1 = [fc[0] - (land[0] - 960) / (s1 / 100), fc[1] - (land[1] - 540) / (s1 / 100)]
        punches.append(dict(item=idx, t=round(tp, 3), a0=it['anchor'], s0=s0, fc=[round(a1[0], 1), round(a1[1], 1)], s1=round(s1, 1), rot=0, dur=.22,
                            hold=round(max(.1, it['t1'] - (tp + .22)), 2), k=o['k']))
        it['punched'] = True

    subs = []
    for o in TL['blocks']:
        v = o.get('voice'); ch = [c for c in (o.get('sub') or []) if c]
        if not v or not ch: continue
        words = TR.get(o['k'], {}).get('words') or []
        ts = chunk_times(words, ch) if words else [(v['t1'] - v['t0']) * sum(len(c) for c in ch[:i]) / max(1, sum(map(len, ch))) for i in range(len(ch))]
        lim = v['t0'] + o['bigt'] - .05 if (o.get('big') and o.get('bigt') is not None) else v['t1'] + .35
        for i, c in enumerate(ch):
            t0 = v['t0'] + (ts[i] or 0) - (.05 if i else -.05)
            t1 = min(v['t0'] + ts[i + 1] - .04 if i + 1 < len(ch) and ts[i + 1] else lim, lim)
            if t1 - t0 < .45: continue
            subs.append(dict(text=c, t0=round(t0, 3), t1=round(t1, 3), k=o['k']))
    for s in subs:
        if s['k'] in blk_end: s['t1'] = round(min(s['t1'], blk_end[s['k']] - .05), 3)   # 絵が黒へ消えた後に字幕を残さない
    for a, b in zip(subs, subs[1:]):
        if a['t1'] > b['t0'] - .06: a['t1'] = round(b['t0'] - .06, 3)
    bad = [s['text'] for s in subs if '。' in s['text'] or '、' in s['text']]
    if bad: print('字幕に句読点があります（外す）:', bad)

    names = [x for o in TL['blocks'] for x in o.get('names', [])]
    if isinstance(S.get('letterbox_open'), str):           # letterbox_open: この場面の頭で黒帯を開いて全面に（山場は枠を外す）
        S['letterbox_open'] = next(round(o['T'], 3) for o in TL['blocks'] if o.get('k') == S['letterbox_open'])
    bars = [dict(t0=round(o['voice']['t0'] - .5, 3), t1=round(o['end'], 3)) for o in TL['blocks'] if o['t'] == 'fx' and o.get('voice')] if S['letterbox'] else []
    checks = sorted({round(b['t'] + 1.0, 2) for b in bigs} | {round(x['t0'] + .9, 2) for x in names} | {round(s['t0'] + .5, 2) for s in subs[::3]}
                    | {round(f['t0'] + min(2.5, (f['t1'] - f['t0']) / 2), 2) for f in fxl})
    D = dict(name=P.out_name(), total=TL['total'], fps=fps, style=S, items=items, fx=fxl, punches=punches, bigs=bigs, subs=subs, names=names, bars=bars,
             checktimes=checks, audio=str(P.build / 'mix.wav'), root=str(P.root))
    P.jsave('_comp.json', D)
    print('絵', len(items), '場面', len(fxl), '寄り', len(punches), '強調', len(bigs), '字幕', len(subs), '名前', len(names))
    if shortened: print('編集点のため溶かす長さを縮めた所（コマ）', shortened)
    return D
