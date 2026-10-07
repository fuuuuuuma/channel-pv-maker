"""下見の動画から一覧画像（コマを格子に並べたもの）を作る。差し込みの絵・高速連打の絵・焼き込みの字幕の位置を目で選ぶのに使う。
  pv.py sheets [ID ...] [--every 10]      → research/sheets/<ID>_<n>.jpg（1枚 6×5＝30コマ・各コマに秒）
  pv.py frames <ID> 秒,秒,...             → research/frames/<ID>_<秒>.jpg（指定の秒のコマを原寸で）"""
import subprocess
import numpy as np
from PIL import Image, ImageDraw
from . import env
from .project import probe_dur


def sheets(P, vids=None, every=10.0):
    out = P.research / 'sheets'; out.mkdir(parents=True, exist_ok=True)
    vids = vids or sorted(d.name for d in P.harvest.iterdir() if (d / 'src.mp4').exists())
    W, H, C, R = 320, 180, 6, 5
    for vid in vids:
        src = P.harvest / vid / 'src.mp4'
        dur = probe_dur(src)
        raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-i', str(src), '-vf', f'fps=1/{every},scale={W}:{H}', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'], capture_output=True).stdout
        fr = np.frombuffer(raw, np.uint8).reshape(-1, H, W, 3)
        for n in range(0, len(fr), C * R):
            g = fr[n:n + C * R]; sheet = Image.new('RGB', (W * C, H * R), (20, 20, 20))
            for j, f in enumerate(g):
                im = Image.fromarray(f); t = (n + j) * every
                ImageDraw.Draw(im).text((5, 4), f'{int(t // 60)}:{t % 60:04.1f} ({t:.0f}s)', fill=(255, 230, 0))
                sheet.paste(im, ((j % C) * W, (j // C) * H))
            sheet.save(out / f'{vid}_{n // (C * R)}.jpg', quality=78)
        print('一覧', vid, f'{dur:.0f}秒', (len(fr) + C * R - 1) // (C * R), '枚', flush=True)


def frames(P, vid, times):
    out = P.research / 'frames'; out.mkdir(parents=True, exist_ok=True)
    src = P.harvest / vid / 'src.mp4'
    for t in times:
        p = out / f'{vid}_{t:.1f}.jpg'
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-ss', f'{t:.2f}', '-i', str(src), '-frames:v', '1', str(p)], check=True)
        print(p)
