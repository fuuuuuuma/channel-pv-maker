"""強調テロップの「かすれ」の質感（ピンク×赤のまだら＋横の擦れ＋白い飛沫）を作る。初回の描画で自動に作られる。"""
import numpy as np
from PIL import Image, ImageFilter

S = 1024


def _noise(sx, sy, seed):
    r = np.random.default_rng(seed).random((S // sy + 2, S // sx + 2))
    return np.array(Image.fromarray((r * 255).astype(np.uint8)).resize((S, S), Image.BICUBIC)).astype(np.float32) / 255


def _fbm(seed, base=96):
    return sum(_noise(base // (2 ** i), base // (2 ** i), seed + i) * (.5 ** i) for i in range(5)) / 1.94


def _one(c1, c2, seed, amt):
    n = _fbm(seed)
    red = np.clip((n - (.62 - amt)) * 9, 0, 1)
    img = np.array(c1, np.float32) * (1 - red[..., None]) + np.array(c2, np.float32) * red[..., None]
    streak = _noise(90, 3, seed + 10) * .7 + _noise(30, 2, seed + 11) * .3
    white = np.clip((streak - .70) * 12, 0, 1) * np.clip((_fbm(seed + 20, 24) - .38) * 6, 0, 1)
    white = np.clip(white + np.clip((_noise(3, 3, seed + 30) - .93) * 30, 0, 1), 0, 1)
    dark = np.clip((_noise(4, 4, seed + 40) - .95) * 40, 0, 1) * .8
    img = img * (1 - white[..., None]) + 255 * white[..., None]
    img = img * (1 - dark[..., None]) + np.array([30, 0, 15], np.float32) * dark[..., None]
    return Image.fromarray(np.clip(img, 0, 255).astype(np.uint8)).filter(ImageFilter.GaussianBlur(.5))


def make(out):
    out.mkdir(parents=True, exist_ok=True)
    _one((255, 34, 214), (232, 8, 42), 11, .12).save(out / 'grunge_pink.png')
    _one((232, 8, 36), (255, 40, 205), 23, .10).save(out / 'grunge_red.png')
