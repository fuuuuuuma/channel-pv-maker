"""質感のある地を 1 枚の PNG に作る（黒や単色の地は安く見える。紙・石目・大理石の地に写真と文字を置くと上位の作例に近づく）。
  pv.py texture paper  --color '#efe7da' --out assets/tex/paper.png
  pv.py texture stone  --color '#9aa79a' --out assets/tex/sage.png
  pv.py texture marble --color '#f1ece4' --out assets/tex/marble.png
場面では scenes.json の "back": {"img": "assets/tex/paper.png"} で敷く（場面が替わっても止まって見える）。
"""
import numpy as np
from PIL import Image
from scipy import ndimage

W, H = 1920, 1080


def _noise(rng, scale, octaves=5, persist=.55):
    """なめらかな値のノイズ（大きな模様から細かい模様まで重ねる）。0〜1"""
    out = np.zeros((H, W), np.float32); amp, tot = 1., 0.
    for o in range(octaves):
        gh, gw = max(2, int(H / scale * 2 ** o)), max(2, int(W / scale * 2 ** o))
        g = rng.random((gh, gw)).astype(np.float32)
        out += amp * ndimage.zoom(g, (H / gh, W / gw), order=3)[:H, :W]; tot += amp; amp *= persist
    out /= tot
    return (out - out.min()) / (out.max() - out.min() + 1e-6)


def _hex(c):
    c = c.lstrip('#'); return np.array([int(c[i:i + 2], 16) for i in (0, 2, 4)], np.float32)


def make(kind, color, out, seed=7, strength=1.):
    rng = np.random.default_rng(seed); base = _hex(color)
    if kind == 'paper':     # 紙：大きなむら＋繊維（横に伸ばしたノイズ）＋細かい粒
        mott = _noise(rng, 420, 4) - .5
        fib = ndimage.gaussian_filter(rng.random((H, W)).astype(np.float32), (1.2, 3.5)) - .5
        grain = rng.random((H, W)).astype(np.float32) - .5
        lum = 1 + strength * (mott * .08 + fib * .16 + grain * .03)
    elif kind == 'stone':   # 石目：むらと斑点
        mott = _noise(rng, 300, 6) - .5
        spk = (rng.random((H, W)) > .9965).astype(np.float32); spk = ndimage.gaussian_filter(spk, .8) * 3
        lum = 1 + strength * (mott * .16 - spk * .08 + (rng.random((H, W)).astype(np.float32) - .5) * .03)
    elif kind == 'marble':  # 大理石：うねった細い筋
        tur = _noise(rng, 520, 6); yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)
        vein = np.abs(np.sin((xx * .004 + yy * .0022) * np.pi + tur * 7.5)) ** .28
        lum = 1 + strength * ((vein - 1) * .14 + (_noise(rng, 360, 4) - .5) * .06)
    else:
        raise SystemExit(f'種類は paper / stone / marble: {kind}')
    yy, xx = np.mgrid[0:H, 0:W].astype(np.float32)               # 周辺を少しだけ暗く（奥行き）
    vig = 1 - .07 * (((xx - W / 2) / (W / 2)) ** 2 + ((yy - H / 2) / (H / 2)) ** 2)
    img = np.clip(base[None, None, :] * (lum * vig)[:, :, None], 0, 255).astype(np.uint8)
    from pathlib import Path
    Path(out).parent.mkdir(parents=True, exist_ok=True)
    Image.fromarray(img).save(out)
    print('地 →', out)
