"""音を作る：出演者の声（voc/）＋音楽＋効果音＋環境音 → build/mix.wav（既定 -14 LUFS・ピーク -1dB）と build/stems/（声・音楽・効果音）。
音楽と効果音の置き場所は build/audio.json。時刻は「ブロック名.T（始まり）/.end（終わり）/.voice（声の始まり）」か秒、後ろに +秒 -秒。
  {"music": [{"file": "assets/music/a.mp3", "from": 0, "at": "A01.T", "until": "title.T", "gain": -2, "fade_in": 1.5, "fade_out": 0.5}],
   "sfx":   [{"file": "assets/sfx/rip.mp3", "at": "tear.T+2.6", "gain": -4}],
   "ambience": [{"file": "assets/sfx/room.mp3", "at": 0, "until": "tear.T+2.7", "gain": -14, "loop": true}],
   "boost": [{"from": "voices.T", "to": "xwall.end", "db": 4}],
   "auto": {"punch": "assets/sfx/whoosh.mp3", "punch_gain": -17, "big": "assets/sfx/hit.mp3", "big_gain": -12},
   "force_end": {"C16": 1349.65}}
声の決まり：頭は 30〜60ms、終わりは余韻に合わせて 100〜350ms のフェード（プツンと始まらない・終わらない）。
語尾は余韻が消えるまで伸ばすが、次の言葉と元動画の編集点の手前で止める。"""
import json, re, subprocess
import numpy as np
from . import env
from .checks import cuts_in

SR = 48000
PAD, TAIL = 0.5, 1.0
db = lambda x: 10 ** (x / 20)


def load(path, ss=None, to=None):
    cmd = [env.ffmpeg(), '-v', 'error']
    if ss is not None: cmd += ['-ss', f'{max(0, ss):.3f}']
    if to is not None: cmd += ['-to', f'{to:.3f}']
    cmd += ['-i', str(path), '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-']
    return np.frombuffer(subprocess.run(cmd, capture_output=True, check=True).stdout, np.float32).reshape(-1, 2).copy()


def fade(a, fi=0., fo=0.):
    if fi: k = min(len(a), int(fi * SR)); a[:k] *= (np.sin(np.linspace(0, np.pi / 2, k)) ** 2)[:, None]
    if fo: k = min(len(a), int(fo * SR)); a[len(a) - k:] *= (np.cos(np.linspace(0, np.pi / 2, k)) ** 2)[:, None]
    return a


def put(bus, a, t, g=0.):
    i = int(round(t * SR))
    if i < 0: a = a[-i:]; i = 0
    if i >= len(bus) or not len(a): return
    a = a[:len(bus) - i]; bus[i:i + len(a)] += a * db(g)


def tail_end(x, b_rel, limit):
    """語尾の余韻が消える位置（voc ファイル内の秒）。20ms ごとの音量が山から 38dB 下がって 60ms 続いた所＋50ms。limit は越えない"""
    m = np.abs(x).mean(1); hop = int(.02 * SR)
    i0, i1 = int(b_rel * SR), min(len(m), int(limit * SR))
    if i1 - i0 < 3 * hop: return limit
    fr = np.array([np.sqrt(np.mean(m[i:i + hop] ** 2)) + 1e-9 for i in range(i0, i1 - hop, hop)])
    dbs = 20 * np.log10(fr); peak = 20 * np.log10(np.sqrt(np.mean(m[max(0, i0 - int(.4 * SR)):i0] ** 2)) + 1e-9)
    q = dbs < peak - 38
    for k in range(len(q) - 2):
        if q[k] and q[k + 1] and q[k + 2]: return min(limit, b_rel + k * .02 + .05)
    return b_rel + int(np.argmin(dbs)) * .02 + .01


def run(P):
    TL = P.tl; BL = P.blocks(); N = int(SR * TL['total'])
    A = P.jload('audio.json', {}); S = P.style()
    W = P.jload('words.json', {}); comp = P.jload('_comp.json', {})
    hard = {p['blk'] for p in TL['pics'] if p.get('hard') and p.get('first')}

    def ref(s):
        if isinstance(s, (int, float)): return float(s)
        m = re.fullmatch(r'\s*([\w-]+)\.(T|end|voice|vend)((?:\s*[+-]\s*[\d.]+)*)\s*', str(s))   # 足し引きは何段でも（hand.T+4.4+0.3）
        if not m: return float(s)
        b = BL[m.group(1)]
        base = {'T': b['T'], 'end': b['end'], 'voice': (b.get('voice') or {}).get('t0', b['T']), 'vend': (b.get('voice') or {}).get('t1', b['end'])}[m.group(2)]
        return base + sum(float(x.replace(' ', '')) for x in re.findall(r'[+-]\s*[\d.]+', m.group(3)))

    vo, mu, fx = (np.zeros((N, 2), np.float32) for _ in range(3))
    from scipy.signal import butter, sosfilt
    hp = butter(2, 75, 'highpass', fs=SR, output='sos')
    tails = {}
    for o in TL['blocks']:
        v = o.get('voice')
        if not v: continue
        dur = v['b'] - v['a']
        full = load(P.build / 'voc' / f"{o['k']}.wav")
        ws = W.get(o['k'], {}).get('words', [])
        nxt = [w[0] for w in ws if w[0] > v['b'] + .02]
        lim_t = min(nxt) - .03 if nxt else v['b'] + TAIL - .05
        try:                                                     # 元動画の編集点（別のカットの音）の手前で止める
            name, sa = P.seg_for(v['vid'], v['b'] - .1, v['b'] + .9)
            c = [v['b'] - .1 + x for x in cuts_in(P.src / f'{name}.mov', v['b'] - .1 - sa, 1.0)]
            if c: lim_t = min(lim_t, min(c) - .02)
        except SystemExit: pass
        if [w for w in ws if w[0] < v['b'] and w[1] > v['b'] + .06]: lim_t = min(lim_t, v['b'] + .04)   # 終わりにまたがる語＝すぐ次の言葉
        limit = PAD + max(.03, min(dur + TAIL - .05, lim_t - v['a']))
        end = max(PAD + dur + .03, tail_end(full, PAD + dur, limit))
        if o['k'] in A.get('force_end', {}): end = PAD + A['force_end'][o['k']] - v['a']
        tails[o['k']] = round(end - PAD - dur, 3)
        pre = 0. if o['k'] in hard else .05                     # 声の頭が編集点ちょうどの所は手前を含めない
        seg = sosfilt(hp, full[int((PAD - pre) * SR):int(end * SR)].copy(), axis=0).astype(np.float32)
        m = np.abs(seg).mean(1); k = int(.05 * SR)
        fr = np.sqrt(np.convolve(m ** 2, np.ones(k) / k, mode='same'))
        rms = np.sqrt((seg[fr > np.percentile(fr, 40)] ** 2).mean()) + 1e-9
        seg *= db(-20) / rms
        seg = fade(seg, .06 if pre else .03, max(.1, min(.35, tails[o['k']] + .05)))
        put(vo, seg, v['t0'] - pre)

    def place(bus, cue, default_gain):
        f = P.root / cue['file']
        if not f.exists(): print('音のファイルが無い', f); return
        at = ref(cue.get('at', 0)); src0 = float(cue.get('from', 0))
        length = (ref(cue['until']) - at) if 'until' in cue else (float(cue['to']) - src0 if 'to' in cue else None)
        if cue.get('loop'):
            one = load(f); need = int((length or 10) * SR)
            a = np.concatenate([one] * (need // max(1, len(one)) + 1))[:need]
        else:
            a = load(f, src0, src0 + length if length else None)
        put(bus, fade(a, float(cue.get('fade_in', 0)), float(cue.get('fade_out', 0))), at, float(cue.get('gain', default_gain)))

    for c in A.get('music', []): place(mu, c, 0)
    for c in A.get('ambience', []): place(fx, c, -14)
    for c in A.get('sfx', []): place(fx, c, -12)
    auto = A.get('auto', {})
    if auto.get('punch'):
        for pz in comp.get('punches', []): place(fx, dict(file=auto['punch'], at=pz['t'] - .05, gain=auto.get('punch_gain', -17)), -17)
    if auto.get('big'):
        for bg in comp.get('bigs', []): place(fx, dict(file=auto['big'], at=bg['t'] - .02, gain=auto.get('big_gain', -12)), -12)
    for b in A.get('boost', []):                                # 声の無い所で音楽を少し大きく（なだらかに）
        g = np.zeros(N, np.float32); i0, i1 = max(0, int(ref(b['from']) * SR)), min(N, int(ref(b['to']) * SR))
        if i1 <= i0: continue
        r = min(int(.6 * SR), (i1 - i0) // 2); g[i0:i1] = 1
        if r > 0: g[i0:i0 + r] = np.linspace(0, 1, r); g[i1 - r:i1] = np.linspace(1, 0, r)
        mu *= (1 + (db(float(b.get('db', 4))) - 1) * g)[:, None]

    m_ = np.abs(mu).max(1); n_ = len(m_) // SR; sec = m_[:n_ * SR].reshape(n_, SR).max(1)
    quiet, st = [], None                                       # 音楽が鳴っていない 2 秒以上の区間（意図した無音でなければ曲を足す）
    for i, v in enumerate(list(sec) + [1]):
        if v < 1e-4 and st is None: st = i
        if v >= 1e-4 and st is not None:
            if i - st >= 2: quiet.append((st, i))
            st = None
    if quiet: print('音楽が鳴っていない区間（秒）', quiet)
    env_ = np.convolve(np.abs(vo).max(axis=1), np.ones(int(.03 * SR)) / int(.03 * SR), mode='same')   # 声の下で音楽を下げる
    g = np.clip(env_ / .02, 0, 1); out = np.empty_like(g); au, ad = np.exp(-1 / (.06 * SR)), np.exp(-1 / (.45 * SR)); s = 0.
    for i in range(0, len(g), 48):
        x = g[i:i + 48].max(); s = au * s + (1 - au) * x if x > s else ad * s + (1 - ad) * x; out[i:i + 48] = s
    mu *= (1 - (1 - db(A.get('duck_db', -10))) * out)[:, None]

    ST = P.build / 'stems'; ST.mkdir(exist_ok=True)
    mgain, fgain = db(A.get('music_db', -6)), db(A.get('sfx_db', -6))
    mix = vo + mu * mgain + fx * fgain

    def write(a, p, norm=False):
        raw = P.build / '_mix_raw.wav'
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-f', 'f32le', '-ac', '2', '-ar', str(SR), '-i', '-', str(raw)], input=a.astype(np.float32).tobytes(), check=True)
        if not norm: raw.replace(p); return
        L = S.get("loudness", -14)          # ピークは -2（書き出しの AAC で 0.5〜1dB 持ち上がるので、仕上がりで -1 以下に収める）
        m = subprocess.run([env.ffmpeg(), '-hide_banner', '-i', str(raw), '-af', f'loudnorm=I={L}:TP=-2:LRA=11:print_format=json', '-f', 'null', '-'], capture_output=True, text=True).stderr
        j = json.loads(m[m.rindex('{'):m.rindex('}') + 1])
        af = (f"loudnorm=I={L}:TP=-2:LRA=11:measured_I={j['input_i']}:measured_TP={j['input_tp']}:measured_LRA={j['input_lra']}"
              f":measured_thresh={j['input_thresh']}:offset={j['target_offset']}:linear=true"
              f",aresample={SR},alimiter=limit=0.79:attack=5:release=50:level=0")   # 線形で TP を守れない曲でも -2dB で止める（実例 -0.9 になった）
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-i', str(raw), '-af', af, '-ar', str(SR), str(p)], check=True)
        raw.unlink()

    write(vo, ST / 'voice.wav'); write(mu * mgain, ST / 'music.wav'); write(fx * fgain, ST / 'sfx.wav')
    write(mix, P.build / 'mix.wav', norm=True)
    print('mix.wav', TL['total'], '秒  語尾の伸ばし', tails)
