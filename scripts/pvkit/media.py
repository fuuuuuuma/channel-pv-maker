"""本番素材の取得と声の下ごしらえ。
  fetch        segments.json の区間を YouTube の 1080p で取得 → build/src/<ID>_<始>_<終>.mov（ProRes 422 HQ・30fps）と .wav
  voices       発言ごとに声だけを抜き出す（demucs で元動画の BGM を外す）→ build/voc/<ブロック>.wav（頭に 0.5 秒・尻に 1.0 秒の余白）
  words        発言の前後 1.5 秒を語の時刻つきで起こす → build/words.json（語尾をどこまで伸ばすか・次の言葉の位置）
  transcripts  発言そのものを高精度で起こす → build/transcripts.json（字幕の切り替え時刻を合わせる）
"""
import json, shutil, subprocess, sys, time
from concurrent.futures import ThreadPoolExecutor
import numpy as np
from . import env, asr

PAD, TAIL = 0.5, 1.0
FMT = 'bv*[height=1080][vcodec^=vp09]+ba/bv*[height=1080][vcodec^=vp9]+ba/bv*[height=1080]+ba/bv*[height>=1080]+ba/b[height>=1080]/bv*+ba/b'


def fetch(P, jobs=3):
    P.src.mkdir(parents=True, exist_ok=True)
    fps = P.style()['fps']

    def job(seg):
        vid, a, b = seg; n = f'{vid}_{a:.2f}_{b:.2f}'
        mov, wav = P.src / f'{n}.mov', P.src / f'{n}.wav'
        if mov.exists() and wav.exists(): return n, 'skip'
        raw = P.src / f'{n}.raw.mkv'; err = ''
        for i in range(6):
            if raw.exists(): break
            r = subprocess.run([env.ytdlp(), '--no-update', '--extractor-args', 'youtube:player_client=web_embedded,default', '-f', FMT,
                                '--download-sections', f'*{a:.2f}-{b:.2f}', '--force-keyframes-at-cuts', '--merge-output-format', 'mkv',
                                '-o', str(raw), f'https://youtu.be/{vid}'], capture_output=True, text=True)
            err = r.stderr.strip()[-200:]
            if not raw.exists(): time.sleep(8 + i * 6)
        if not raw.exists(): return n, 'FAIL ' + err
        h = subprocess.run([env.ffprobe(), '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=height', '-of', 'csv=p=0', str(raw)], capture_output=True, text=True).stdout.strip()
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-i', str(raw), '-vf', f'fps={fps},scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,pad=1920:1080:(ow-iw)/2:(oh-ih)/2',
                        '-c:v', 'prores_ks', '-profile:v', '3', '-pix_fmt', 'yuv422p10le', '-an', str(mov)], check=True)
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-i', str(raw), '-vn', '-ac', '2', '-ar', '48000', str(wav)], check=True)
        raw.unlink()
        return n, f'ok {h}p'

    bad = 0
    with ThreadPoolExecutor(jobs) as ex:
        for n, st in ex.map(job, P.segs):
            if st != 'skip': print(n, st, flush=True)
            bad += st.startswith('FAIL')
    print('取得', len(P.segs), '区間', f'（失敗 {bad}）' if bad else '')


def demucs_device():
    if env.apple_silicon(): return 'mps'
    try:
        import torch
        return 'cuda' if torch.cuda.is_available() else 'cpu'
    except Exception: return 'cpu'


def voices(P):
    IN = P.build / 'voc_in'; IN.mkdir(exist_ok=True)
    OUT = P.build / 'voc'; OUT.mkdir(exist_ok=True)
    todo = []
    for o in P.tl['blocks']:
        v = o.get('voice')
        if not v or (OUT / f"{o['k']}.wav").exists(): continue
        a, b = v['a'] - PAD, v['b'] + TAIL
        name, sa = P.seg_for(v['vid'], a, b)
        dst = IN / f"{o['k']}.wav"
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-ss', f'{a - sa:.3f}', '-t', f'{b - a:.3f}', '-i', str(P.src / f'{name}.wav'), str(dst)], check=True)
        todo.append(dst)
    print('分ける発言', len(todo))
    if not todo: return
    if not env.has_module('demucs'):
        print('demucs が無いので、元の音のまま使います（元動画の BGM が残る）。pip install demucs で直る')
        for p in todo: shutil.copy(p, OUT / p.name)
        return
    subprocess.run([sys.executable, '-m', 'demucs', '--two-stems', 'vocals', '-n', 'htdemucs', '-d', demucs_device(), '-o', str(P.build / '_demucs')] + [str(p) for p in todo], check=True)
    for p in todo: shutil.copy(P.build / '_demucs' / 'htdemucs' / p.stem / 'vocals.wav', OUT / p.name)


def _wav16(P, path, ss, t):
    raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-ss', f'{max(0, ss):.3f}', '-t', f'{t:.3f}', '-i', str(path), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout
    return np.frombuffer(raw, np.float32)


def words(P):
    out = P.build / 'words.json'
    W = json.load(open(out)) if out.exists() else {}
    for o in P.tl['blocks']:
        v = o.get('voice')
        if not v: continue
        key = f"{o['k']}|{v['vid']}|{v['a']}|{v['b']}"
        if W.get(o['k'], {}).get('key') == key: continue
        name, sa = P.seg_for(v['vid'], v['a'], v['b'])
        sb = next(s[2] for s in P.segs if f'{s[0]}_{s[1]:.2f}_{s[2]:.2f}' == name)
        A, B = max(sa, v['a'] - 1.5), min(sb, v['b'] + 1.5)
        r = asr.transcribe(_wav16(P, P.src / f'{name}.wav', A - sa, B - A), lang=P.lang)
        ws = [[round(A + w[0], 2), round(A + w[1], 2), w[2]] for w in asr.words(r)]
        W[o['k']] = {'key': key, 'words': ws}
        near = lambda t: ' '.join(f'{w[2]}[{w[0]:.2f}]' for w in ws if abs(w[0] - t) < .8 or abs(w[1] - t) < .8)
        print(f"{o['k']:6} 始め {v['a']:.2f}: {near(v['a'])}\n       終わり {v['b']:.2f}: {near(v['b'])}", flush=True)
    json.dump(W, open(out, 'w'), ensure_ascii=False, indent=1)
    print('words.json', len(W))


def transcripts(P):
    out = P.build / 'transcripts.json'
    T = json.load(open(out)) if out.exists() else {}
    for o in P.tl['blocks']:
        v = o.get('voice')
        if not v: continue
        key = f"{o['k']}|{v['vid']}|{v['a']}|{v['b']}"
        if T.get(o['k'], {}).get('key') == key: continue
        a = _wav16(P, P.build / 'voc' / f"{o['k']}.wav", PAD - .05, v['b'] - v['a'] + .15)
        r = asr.transcribe(a, lang=P.lang, quality='best')
        T[o['k']] = dict(key=key, text=r['text'], words=[[round(w[0] - .05, 2), round(w[1] - .05, 2), w[2]] for w in asr.words(r)])
        print(o['k'], r['text'], flush=True)
    json.dump(T, open(out, 'w'), ensure_ascii=False, indent=1)
