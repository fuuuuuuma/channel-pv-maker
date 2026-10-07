"""書き出した動画の検品。
  1) 音量（LUFS）と、全コマの明るさの「1〜2 コマだけの跳ね」（白い閃光・一瞬の黒）を数える（0 件が合格）
  2) すべての切り替え・寄り・名前・強調の前後 ±0.25 秒を 1 コマずつ並べた一覧 → build/_qa/cut_*.jpg（切れ端・焼き込み・顔の切れを目で見る）
  3) 高速の連打は全コマを並べる → build/_qa/montage_*.jpg
  4) 声だけ（stems/voice.wav）を発言ごとに区切って文字起こし → build/_qa/voices.txt（頭と終わりに別の言葉が混ざっていないか）"""
import json, re, shutil, subprocess
import numpy as np
from PIL import Image, ImageDraw
from . import env, asr


def run(P, video=None, no_asr=False):
    D = P.jload('_comp.json'); TL = P.tl
    V = video or str(P.exports / f"{D['name']}.mp4")
    OUT = P.build / '_qa'; shutil.rmtree(OUT, ignore_errors=True); OUT.mkdir()
    fps = D['fps']
    m = subprocess.run([env.ffmpeg(), '-hide_banner', '-i', V, '-af', 'ebur128=peak=true', '-f', 'null', '-'], capture_output=True, text=True).stderr
    I = re.findall(r'I:\s+(-?[\d.]+) LUFS', m); pk = re.findall(r'Peak:\s+(-?[\d.]+) dBFS', m)
    print('音量', (I[-1] + ' LUFS') if I else '?', ' ピーク', (pk[-1] + ' dBFS') if pk else '?')
    raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-i', V, '-vf', 'scale=64:36,format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    Y = np.frombuffer(raw, np.uint8).reshape(-1, 36 * 64).astype(float).mean(1)
    spikes = [(round(i / fps, 3), round(Y[i - 1]), round(Y[i]), round(Y[i + 1])) for i in range(2, len(Y) - 2)
              if abs(Y[i] - (Y[i - 2] + Y[i + 2]) / 2) > 25 and abs(Y[i] - Y[i - 1]) > 18 and abs(Y[i] - Y[i + 1]) > 18]
    print(f'コマ数 {len(Y)}  明るさの跳ね {len(spikes)} 件', spikes[:10])
    blacks, run_ = [], None
    for i, y in enumerate(Y):
        if y < 3 and run_ is None: run_ = i
        if (y >= 3 or i == len(Y) - 1) and run_ is not None:
            if 1 <= i - run_ < int(.3 * fps) and i < len(Y) - fps // 2: blacks.append((round(run_ / fps, 2), round((i - run_) / fps, 2)))   # 最後の黒は除く
            run_ = None
    if blacks: print('0.3 秒未満の真っ黒（一瞬の抜けに見えないか確かめる）', blacks)
    json.dump({'frames': len(Y), 'spikes': spikes, 'short_blacks': blacks}, open(OUT / 'luma.json', 'w'))

    P_ = [p for p in TL['pics'] if p.get('look') != 'cut']
    cuts = sorted({round(p['t0'], 3) for p in P_} | {round(p['t1'], 3) for p in P_} | {round(q['t'] + .1, 3) for q in D['punches']}
                  | {round(x['t0'] + .15, 3) for x in D['names']} | {round(b['t'] + .05, 3) for b in D['bigs']})
    n = int(round(.25 * fps))
    for c in cuts:
        c0 = max(0, c - .25)
        raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-ss', f'{c0:.3f}', '-i', V, '-frames:v', str(2 * n + 1), '-vf', 'scale=320:180', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, 180, 320, 3)
        if not len(fr): continue
        sheet = Image.new('RGB', (320 * 8, 180 * ((len(fr) + 7) // 8)))
        for j, f in enumerate(fr):
            im = Image.fromarray(f); ImageDraw.Draw(im).text((4, 4), f'{c0 + j / fps:.2f}', fill=(255, 60, 60)); sheet.paste(im, ((j % 8) * 320, (j // 8) * 180))
        sheet.save(OUT / f'cut_{c:07.2f}.jpg', quality=80)
    print('切り替えの一覧', len(cuts), '枚 →', OUT)

    M = [p for p in TL['pics'] if p.get('look') == 'cut']
    if M:
        a0, a1 = M[0]['t0'] - .2, M[-1]['t1'] + .5
        raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-ss', f'{a0:.3f}', '-i', V, '-t', f'{a1 - a0:.3f}', '-vf', 'scale=240:135', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, 135, 240, 3)
        for part in range(0, len(fr), 144):
            g = fr[part:part + 144]; sheet = Image.new('RGB', (240 * 12, 135 * ((len(g) + 11) // 12)))
            for j, f in enumerate(g):
                im = Image.fromarray(f); ImageDraw.Draw(im).text((3, 3), f'{a0 + (part + j) / fps:.2f}', fill=(255, 60, 60)); sheet.paste(im, ((j % 12) * 240, (j // 12) * 135))
            sheet.save(OUT / f'montage_{part // 144}.jpg', quality=80)
        print('連打の全コマ', len(fr))

    vw = P.build / 'stems' / 'voice.wav'
    if no_asr or not vw.exists(): return
    a = np.frombuffer(subprocess.run([env.ffmpeg(), '-v', 'error', '-i', str(vw), '-ac', '1', '-ar', '16000', '-f', 'f32le', '-'], capture_output=True).stdout, np.float32)
    Vs = [o for o in TL['blocks'] if o.get('voice')]
    with open(OUT / 'voices.txt', 'w') as f:
        for i, o in enumerate(Vs):
            v = o['voice']; nx = Vs[i + 1]['voice']['t0'] - .08 if i + 1 < len(Vs) else v['t1'] + 1.2
            pv = Vs[i - 1]['voice']['t1'] + .02 if i else 0
            seg = a[int(max(pv, v['t0'] - .3) * 16000):int(min(v['t1'] + 1.2, nx) * 16000)]
            if len(seg) < 1600: continue
            line = f"{o['k']:7} | {asr.transcribe(seg.copy(), lang=P.lang)['text'].strip()}"
            print(line, flush=True); f.write(line + '\n')
    print('声の文字起こし →', OUT / 'voices.txt', '（字幕の区切りと比べ、頭と終わりに余計な言葉が無いか見る）')


def preview(P, video=None, mb=27):
    """スマホで見られる軽い確認版（720p・約 mb MB）"""
    D = P.jload('_comp.json'); V = video or str(P.exports / f"{D['name']}.mp4")
    out = P.exports / f"{D['name']}_preview.mp4"
    kbps = int(mb * 8000 / D['total']) - 96
    subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-i', V, '-vf', 'scale=1280:-2', '-c:v', 'libx264', '-preset', 'slow', '-b:v', f'{kbps}k', '-maxrate', f'{int(kbps * 1.4)}k',
                    '-bufsize', f'{kbps * 3}k', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '96k', '-movflags', '+faststart', str(out)], check=True)
    print('確認版 →', out, f'{out.stat().st_size / 1e6:.0f}MB')
