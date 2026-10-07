"""組み立て前の点検。
  edges   元動画の編集点（ジャンプカット）を探す。発言の頭と終わり・各カットの始めと終わりに、前後のカットの切れ端（数コマ）が入らないか
  faces   黒帯（2.39:1）や拡大で演者の顔が切れていないか。切れるカットは framing.json に入れる案を出す
  crops   framing.json を当てた「完成時に見える絵」を各カットの始め・中・終わりで並べる → build/_frames/crop_*.jpg
"""
import json, subprocess
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from . import env

W, H = 96, 54


def cuts_in(path, ss, t, fps=30):
    """素材の ss 秒から t 秒の間の編集点（新しいカットの最初のコマの、ss からの秒）"""
    raw = subprocess.run([env.ffmpeg(), '-v', 'error', '-ss', f'{max(0, ss):.3f}', '-i', str(path), '-t', f'{t:.3f}', '-vf', f'scale={W}:{H},format=gray', '-f', 'rawvideo', '-'], capture_output=True).stdout
    x = np.frombuffer(raw, np.uint8).reshape(-1, H, W).astype(np.float32)
    if len(x) < 3: return []
    d = np.abs(np.diff(x, axis=0)).mean((1, 2)); med = np.median(d) + .5
    return [round((i + 1) / fps, 3) for i in range(len(d)) if d[i] > 11 and d[i] > 6 * med]


def edges(P):
    fps = P.style()['fps']
    print('== 発言の頭と終わりのそばの編集点（a を後ろへ・b を手前へ寄せる案）')
    for o in P.tl['blocks']:
        v = o.get('voice')
        if not v: continue
        name, sa = P.seg_for(v['vid'], v['a'], v['b'])
        lo = max(sa + .05, v['a'] - .3)
        try: c = [lo + x for x in cuts_in(P.src / f'{name}.mov', lo - sa, v['b'] + 1.0 - lo, fps)]
        except Exception: c = []
        head = [x for x in c if v['a'] - .05 < x < v['a'] + .7]
        tail = [x for x in c if v['b'] - .7 < x < v['b'] + 1.0]
        tip = []
        if head and max(head) + 1 / fps > v['a'] + .005: tip.append(f"a → {max(head) + 1 / fps:.2f}（頭に前のカットが入る）")
        if tail: tip.append(f"b ≦ {min(tail) - 1 / (2 * fps):.2f}（終わりのそばに編集点）")
        if tip: print(f"{o['k']:7} a={v['a']} b={v['b']}  " + ' / '.join(tip))
    print('== 各カットの始めと終わりの切れ端（0.6 秒未満）')
    for key, p in P.shots():
        f, off = P.source(p)
        dur = p['t1'] - p['t0']
        c = cuts_in(f, off, dur, fps)
        bad = [t for t in c if t < .6 or t > dur - .6]
        if bad: print(f"{key:9} {p['vid']}@{p['src']} 長さ{dur:.2f} 編集点{c}  ← 切れ端。edl.py で絵の始めを遅らせるか終わりを早める")


def detect(images):
    """画像ごとの顔の枠 [[x0,y0,x1,y1], ...]（左上原点の px）"""
    fb = env.faces_bin()
    if fb:
        out = subprocess.run([fb] + [str(i) for i in images], capture_output=True, text=True).stdout.splitlines()
        return [json.loads(l).get('faces', []) for l in out]
    try:
        import cv2
    except ImportError:
        return [None] * len(images)
    cas = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    res = []
    for i in images:
        g = cv2.cvtColor(cv2.imread(str(i)), cv2.COLOR_BGR2GRAY)
        res.append([[int(x), int(y), int(x + w), int(y + h)] for x, y, w, h in cas.detectMultiScale(g, 1.1, 5, minSize=(60, 60))])
    return res


def faces(P, apply=False):
    tmp = P.build / '_facechk'; tmp.mkdir(exist_ok=True)
    win = P.window(); fix = {}; n_no = 0
    for key, p in P.shots():
        try: f, off = P.source(p)
        except SystemExit as e: print('飛ばす', key, e); continue
        dur = p['t1'] - p['t0']; imgs = []
        for k, frac in enumerate((.15, .5, .85)):
            img = tmp / f"{key.replace('#', '_')}_{k}.png"
            subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-ss', f'{off + dur * frac:.3f}', '-i', str(f), '-frames:v', '1', str(img)], check=True)
            imgs.append(img)
        res = detect(imgs)
        if res[0] is None: n_no += 1; continue
        s, y, x = P.framing(key, p); push = 1.03 if p.get('sync') else 1.0
        vx0, vx1 = 960 + x - win[0] / (s * push), 960 + x + win[0] / (s * push)
        vy0, vy1 = 540 + y - win[1] / (s * push), 540 + y + win[1] / (s * push)
        top = bot = 0
        for fs in res:
            for fx0, fy0, fx1, fy1 in fs:
                h = fy1 - fy0
                if h < 60 or fx1 < vx0 or fx0 > vx1: continue   # 小さな顔（画面の中の画面）と左右の外は見ない
                top = max(top, vy0 - (fy0 - .2 * h)); bot = max(bot, fy1 + .1 * h - vy1)
        if top > 0 or bot > 0:
            ny = round(y - top if top > 0 else y + bot)
            lim = 540 - win[1] / s; ny = int(max(-lim, min(lim, ny)))
            fix[key] = [s, ny, x]
            print(f"切れる {key:9} {p['vid']}@{p['src']}  上 {top:.0f}px 下 {bot:.0f}px  今 [{s},{y},{x}] → [{s},{ny},{x}]")
    if n_no: print('顔検出の道具が無いので見ていないカット:', n_no, '（pv.py doctor）')
    print('切れるカット', len(fix))
    if apply and fix:
        FR = P.jload('framing.json', {}); FR.update(fix); P.jsave('framing.json', FR); print('framing.json に入れました。上下とも切れるものは倍率を下げて手で直す')


def crops(P, keys=None):
    out = P.build / '_frames'; out.mkdir(exist_ok=True)
    try: F = ImageFont.truetype('/System/Library/Fonts/ヒラギノ角ゴシック W6.ttc', 20)
    except Exception: F = ImageFont.load_default()
    win = P.window(); TW, TH = 480, int(480 * win[1] / win[0])
    rows = []
    for key, p in P.shots():
        if keys and key not in keys: continue
        f, off = P.source(p); dur = min(p['t1'] - p['t0'], 6.0)
        s, y, x = P.framing(key, p); w, h = 2 * win[0] / s, 2 * win[1] / s
        row = Image.new('RGB', (TW * 3 + 260, TH + 6), (25, 25, 25)); d = ImageDraw.Draw(row)
        for c, fr in enumerate((.06, .5, .94)):
            img = out / f'c_{key.replace("#", "_")}_{c}.png'
            subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-ss', f'{off + dur * fr:.3f}', '-i', str(f), '-frames:v', '1',
                            '-vf', f'crop={w:.0f}:{h:.0f}:{960 + x - w / 2:.0f}:{540 + y - h / 2:.0f},scale={TW}:{TH}', str(img)], check=True)
            row.paste(Image.open(img), (c * TW, 0))
        d.text((TW * 3 + 10, 8), f'{key} {p.get("look", "")}\n{p["vid"][:8]}@{p["src"]}\n{"同期" if p["sync"] else "差し込み"} {p["t1"] - p["t0"]:.1f}秒\n{s} / {y} / {x}', font=F, fill=(235, 235, 235))
        rows.append(row)
    for k in range(0, len(rows), 11):
        part = rows[k:k + 11]; sheet = Image.new('RGB', (part[0].width, sum(r.height for r in part)))
        yy = 0
        for r in part: sheet.paste(r, (0, yy)); yy += r.height
        sheet.save(out / f'crop_{k // 11}.jpg', quality=82)
    print(len(rows), 'カット →', out)
