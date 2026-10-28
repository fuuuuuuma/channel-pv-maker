"""曲の拍の時刻を JSON に書き出す（映像の切り替えを拍に合わせるため）。
  pv.py beats assets/music/main.wav --out build/beats_main.json
→ {"tempo": 96.0, "beats": [0.52, 1.14, ...], "downbeats": [...4 拍ごと...], "loud": [[秒, dB], ...1 秒ごと]}
edl.py では、切り替えたい秒に近い拍を選んで長さを決める（溶かすなら拍の手前に重ねる）。
"""
import json
from pathlib import Path
import numpy as np


def run(wav, out=None):
    import librosa
    y, sr = librosa.load(wav, sr=22050, mono=True)
    tempo, frames = librosa.beat.beat_track(y=y, sr=sr)
    bt = [round(float(x), 3) for x in librosa.frames_to_time(frames, sr=sr)]
    rms = librosa.feature.rms(y=y, frame_length=2048, hop_length=512)[0]
    t = librosa.frames_to_time(np.arange(len(rms)), sr=sr, hop_length=512)
    loud = [[s, round(float(20 * np.log10(rms[(t >= s) & (t < s + 1)].mean() + 1e-6)), 1)] for s in range(int(len(y) / sr))]
    d = dict(tempo=round(float(np.atleast_1d(tempo)[0]), 2), beats=bt, downbeats=bt[::4], loud=loud)
    out = Path(out or Path(wav).with_suffix('.beats.json'))
    out.write_text(json.dumps(d, ensure_ascii=False))
    print('拍', len(bt), '個・テンポ', d['tempo'], '→', out)
    return d
