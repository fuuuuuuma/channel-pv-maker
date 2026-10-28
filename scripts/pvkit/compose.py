"""After Effects が無いときの書き出し（ffmpeg だけ）。build/_comp.json を読み、AE 版と同じ並びで重ねる。
  1) 絵を 1 本ずつ切り出す（切り取り・夜の色・寄り・溶ける入りと消え）→ build/_ff/items/
  2) 黒い下地に時刻どおり重ねる（12 本ずつ）→ 3) AI 素材・周辺の暗さ・黒帯・場面・強調テロップ・字幕と名前（ASS）→ 4) 音と合わせる
AE 版との違い：話している顔の「ゆっくり寄る」動きは無し。強調の寄りは 0.2 秒の動きではなく一瞬で寄る（スマッシュズーム）。
字幕と名前の札はブラウザで PNG に描き、溶かしながら重ねる（ffmpeg の字幕機能 libass が無くても動く）。名前の札は浮き上がらず溶けるだけ。"""
import json, shutil, subprocess
from pathlib import Path
from . import env
from .project import probe_dur, check_mix

PRO = ['-c:v', 'prores_ks', '-profile:v', '2', '-pix_fmt', 'yuv422p10le']
PRO_A = ['-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le']


def ff(args):
    r = subprocess.run([env.ffmpeg(), '-v', 'error', '-y', *args], capture_output=True, text=True)
    if r.returncode: raise SystemExit('ffmpeg 失敗: ' + r.stderr[-800:])


def frame_vf(scale, anchor, night, s_sharp=True):
    s = scale / 100; ax, ay = anchor
    if s >= 1:
        w, h = 1920 / s, 1080 / s
        x = min(max(0, ax - w / 2), 1920 - w); y = min(max(0, ay - h / 2), 1080 - h)
        vf = f'crop={w:.2f}:{h:.2f}:{x:.2f}:{y:.2f},scale=1920:1080:flags=lanczos'
    else:
        vf = f'scale={1920 * s:.0f}:{1080 * s:.0f},pad=1920:1080:(ow-iw)/2:(oh-ih)/2'
    if night: vf += ',eq=saturation=0.22:brightness=-0.07:contrast=1.06,colorbalance=bs=0.10:bm=0.06:bh=0.03'
    if s_sharp and s > 1.3: vf += ',unsharp=5:5:0.6'
    return vf + ',setsar=1'


def clamp_anchor(fc, s):
    x0, x1, y0, y1 = 960 / s + 10, 1920 - 960 / s - 10, 540 / s + 10, 1080 - 540 / s - 10
    return [max(x0, min(x1, fc[0])), max(y0, min(y1, fc[1]))]


def render_item(i, it, punch, fps, out):
    start = it['off'] - it['pre']; L = it['t1'] - (it['t0'] - it['pre'])
    night = it['look'] == 'night'
    if punch:   # 寄る前と後の 2 つに分けて、つなぐ
        tp = punch['t'] - (it['t0'] - it['pre'])
        a1 = clamp_anchor(punch['fc'], punch['s1'] / 100)
        vf = (f"[0:v]trim=0:{tp:.3f},setpts=PTS-STARTPTS,{frame_vf(it['scale'], it['anchor'], night)}[a];"
              f"[0:v]trim={tp:.3f},setpts=PTS-STARTPTS,{frame_vf(punch['s1'], a1, night)}[b];[a][b]concat=n=2:v=1[c]")
    else:
        vf = f"[0:v]{frame_vf(it['scale'], it['anchor'], night)}[c]"
    fades = []
    if it['fin'] > 0: fades.append(f"fade=t=in:st=0:d={it['fin']:.3f}:alpha=1")
    if it['fout'] > 0: fades.append(f"fade=t=out:st={L - it['fout']:.3f}:d={it['fout']:.3f}:alpha=1")
    vf += f";[c]fps={fps},format=yuva444p10le{',' + ','.join(fades) if fades else ''}[o]"
    ff(['-ss', f'{max(0, start):.3f}', '-t', f'{L:.3f}', '-i', it['file'], '-filter_complex', vf, '-map', '[o]', '-an', *PRO_A, str(out)])


def ai_vf(x, L, fps):
    """AI・フリー素材の動画：src 秒から使い、枠（box）を覆う大きさに合わせ、zoom でゆっくり寄る。枠の外は透明"""
    r = subprocess.run([env.ffprobe(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height', '-of', 'csv=p=0', x['file']], capture_output=True, text=True)
    sw, sh = (int(v) for v in r.stdout.strip().split(',')[:2])
    bx = x.get('box') or [0, 0, 1920, 1080]; z0, z1 = x.get('zoom') or (1, 1)
    cov = max(bx[2] / sw, bx[3] / sh); dx, dy = x.get('shift') or (0, 0)
    if abs(z1 - z0) < 1e-4: sc = f"scale={round(sw * cov * z0 / 2) * 2}:-2:flags=lanczos"
    else: sc = f"scale=w='trunc({sw * cov:.4f}*({z0}+{z1 - z0:.5f}*t/{L:.3f})/2)*2':h=-2:eval=frame:flags=lanczos"
    return (f"trim=start={x.get('src') or 0:.3f}:duration={L:.3f},setpts=PTS-STARTPTS,{sc},crop={bx[2]}:{bx[3]}:max(0\\,(in_w-out_w)/2-{dx}):max(0\\,(in_h-out_h)/2-{dy}),"
            f"fps={fps},format=yuva444p10le,pad=1920:1080:{bx[0]}:{bx[1]}:color=black@0")


def overlay_batch(base, clips, total, fps, out):
    """clips: [(ファイル, 始まりの秒, 追加のフィルタ)]"""
    args = ['-i', str(base)]; fc = []; prev = '0:v'
    for n, (f, t0, extra) in enumerate(clips, 1):
        args += ['-i', str(f)]
        fc.append(f"[{n}:v]{extra + ',' if extra else ''}setpts=PTS-STARTPTS+{t0:.4f}/TB[v{n}]")
        fc.append(f"[{prev}][v{n}]overlay=eof_action=pass:repeatlast=0[o{n}]"); prev = f'o{n}'
    ff([*args, '-filter_complex', ';'.join(fc), '-map', f'[{prev}]', '-t', f'{total:.3f}', '-r', str(fps), *PRO, str(out)])


def text_pngs(P, D, W):
    """字幕と名前の札を 1 枚ずつ透明な PNG に描く（ブラウザ）→ [(png, 始まり, 長さ)]"""
    items = [dict(kind='cap', text=x['text'], t0=x['t0'], t1=x['t1']) for x in D['subs']] + \
            [dict(kind='name', name=x['name'], role=x['role'], t0=x['t0'], t1=x['t1']) for x in D['names']]
    (W / 'texts.json').write_text(json.dumps(items, ensure_ascii=False))
    if items:
        from .render import _node
        _node(P, 'texts', ['texts'])
    return [(W / 'text' / f'{i}.png', x['t0'], x['t1'] - x['t0'], x['kind']) for i, x in enumerate(items)]


def run(P, keep=False):
    D = P.jload('_comp.json'); S = D['style']; fps = D['fps']; total = D['total']
    W = P.build / '_ff'; IT = W / 'items'; IT.mkdir(parents=True, exist_ok=True)
    pun = {p['item']: p for p in D['punches']}
    print('1) 絵を切り出す', len(D['items']), '本', flush=True)
    clips = []
    for i, it in enumerate(D['items']):
        f = IT / f'{i:03d}.mov'
        render_item(i, it, pun.get(i), fps, f)
        clips.append((f, it['t0'] - it['pre'], ''))
    print('2) 時刻どおりに重ねる', flush=True)
    base = W / 'base_0.mov'
    ff(['-f', 'lavfi', '-i', f"color={S.get('base') or 'black'}:s=1920x1080:r={fps}:d={total:.3f}", *PRO, str(base)])
    for n in range(0, len(clips), 12):
        nxt = W / f'base_{n // 12 + 1}.mov'
        overlay_batch(base, clips[n:n + 12], total, fps, nxt); base.unlink(); base = nxt
    print('3) 場面・黒帯・強調・字幕を重ねる', flush=True)
    g = []
    for x in D['fx']:
        if not Path(x['file']).exists(): print('  場面が無い（飛ばす）', x['k']); continue
        if x.get('matte_only'): continue                                    # 文字の形に抜くための場面（それ自体は重ねない）
        L = x['t1'] - x['t0']
        if x['ai']: ex = ai_vf(x, L, fps)
        else: ex = f"trim=0:{L:.3f},setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=increase,crop=1920:1080,fps={fps},format=yuva444p10le"
        if x.get('fade', 0) > 0: ex += f",fade=t=in:st=0:d={x['fade']:.3f}:alpha=1"
        if x['fout'] > 0: ex += f",fade=t=out:st={L - x['fout']:.3f}:d={x['fout']:.3f}:alpha=1"
        if x['ai'] and x.get('matte') and Path(x['matte']).exists():          # 文字の形に抜く（AE 版のトラックマットと同じ）
            mf = W / f"matte_{x['k']}.mov"
            ff(['-i', x['file'], '-i', x['matte'], '-filter_complex',
                f"[0:v]{ex}[a];[1:v]trim=0:{L:.3f},setpts=PTS-STARTPTS,fps={fps},format=yuva444p10le,alphaextract[m];[a][m]alphamerge[o]", '-map', '[o]', *PRO, str(mf)])
            g.append((mf, x['t0'], '', True)); continue
        g.append((x['file'], x['t0'], ex, x['ai']))   # blend（screen など）は AE 版だけ。ここでは普通に重ねる
    # AI 素材 → 周辺の暗さ → 黒帯 → 場面 の順（AE 版と同じ重なり）
    ai = [(f, t, e) for f, t, e, a in g if a]; sc = [(f, t, e) for f, t, e, a in g if not a]
    if ai:
        nxt = W / 'base_ai.mov'; overlay_batch(base, ai, total, fps, nxt); base.unlink(); base = nxt
    vf = []
    if S.get('vignette', 45) > 0: vf.append('vignette=angle=PI/5')
    for b in D['bigs']: vf.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@0.30:t=fill:enable='between(t,{b['t'] - .1:.3f},{b['end']:.3f})'")
    if S.get('letterbox', True):
        o = S.get('letterbox_open')                         # 山場で黒帯を 0.8 秒で開く（plan が場面の名前を秒に直してある）
        k = f"(1-clip((t-{o})/0.8,0,1))" if isinstance(o, (int, float)) else '1'
        vf += [f"drawbox=x=0:y=0:w=iw:h='138*{k}':color=black:t=fill", f"drawbox=x=0:y='1080-139*{k}':w=iw:h='139*{k}':color=black:t=fill"]
    if vf:
        nxt = W / 'base_v.mov'; ff(['-i', str(base), '-vf', ','.join(vf), *PRO, str(nxt)]); base.unlink(); base = nxt
    if sc:
        nxt = W / 'base_fx.mov'; overlay_batch(base, sc, total, fps, nxt); base.unlink(); base = nxt
    if D['bars']:   # 声のある場面は黒帯を被せて字幕を読めるようにする
        vf = [f"drawbox=x=0:y=0:w=iw:h=138:color=black:t=fill:enable='between(t,{b['t0']:.3f},{b['t1']:.3f})',drawbox=x=0:y=941:w=iw:h=139:color=black:t=fill:enable='between(t,{b['t0']:.3f},{b['t1']:.3f})'" for b in D['bars']]
        nxt = W / 'base_bars.mov'; ff(['-i', str(base), '-vf', ','.join(vf), *PRO, str(nxt)]); base.unlink(); base = nxt
    tel = [(b['file'], b['t'], f"trim=0:{b['end'] - b['t']:.3f},setpts=PTS-STARTPTS") for b in D['bigs'] if Path(b['file']).exists()]
    if tel:
        nxt = W / 'base_tel.mov'; overlay_batch(base, tel, total, fps, nxt); base.unlink(); base = nxt
    txt = []
    for png, t0, L, kind in text_pngs(P, D, W):
        fi = .14 if kind == 'cap' else .3; fo = .14 if kind == 'cap' else .22
        txt.append((png, t0, f"loop=-1:1:0,fps={fps},trim=0:{L:.3f},format=yuva444p10le,fade=t=in:st=0:d={fi}:alpha=1,fade=t=out:st={max(0, L - fo):.3f}:d={fo}:alpha=1"))
    for n in range(0, len(txt), 16):
        nxt = W / f'base_txt{n}.mov'; overlay_batch(base, txt[n:n + 16], total, fps, nxt); base.unlink(); base = nxt
    vf = ['null']
    last = [x for x in D['fx'] if x['t1'] >= total - .5]
    if last: vf.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='gte(t,{last[-1]['t1'] - .04:.3f})'")
    ef = S.get('edge_fade', 0)
    if ef > 0: vf += [f'fade=t=in:st=0:d={ef}', f'fade=t=out:st={total - .2 - ef:.3f}:d={ef}']
    P.exports.mkdir(exist_ok=True)
    out = P.exports / f"{D['name']}.mp4"
    print('4) 音と合わせて書き出す', flush=True)
    check_mix(P, total)
    ff(['-i', str(base), '-i', str(P.build / 'mix.wav'), '-vf', ','.join(vf), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow', '-crf', '16',
        '-pix_fmt', 'yuv420p', '-c:a', env.aac(), '-b:a', '320k', '-movflags', '+faststart', '-shortest', str(out)])
    chk = P.build / '_ff_check'; shutil.rmtree(chk, ignore_errors=True); chk.mkdir()
    for t in D['checktimes']:
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', str(out), '-frames:v', '1', str(chk / f'f_{round(t * 100):06d}.png')])
    from .ae import sheet; sheet(chk)
    if not keep: shutil.rmtree(W, ignore_errors=True)
    print('書き出し →', out, f'{probe_dur(out):.1f}秒  確認用のコマ →', chk)
