"""案件フォルダ（pv.project.json がある所）と、timeline.json の絵・素材ファイル・切り取りを結びつける共通処理。

案件フォルダの形（pv.py init が作る）:
  pv.project.json   案件の設定（名前・言語・チャンネル）
  research/         動画の一覧・発言の候補・X の投稿の一覧・一覧画像
  harvest/<動画ID>/ 下見（360p）・音声・文字起こし・概要欄
  assets/           brand（ロゴ・アイコン・バナー）・thumbs（サムネ）・x（投稿の画像）・banners・ai
  planning/         構成表（plan.md）・見本
  build/            edl.py（設計図）・style.json・scenes.json・audio.json・subs.json・framing.json と作業の生成物
  exports/          書き出した動画
"""
import json, os, subprocess
from pathlib import Path
from . import env

MARK = 'pv.project.json'


def find_root(start=None):
    p = Path(start or os.environ.get('PV_PROJECT') or Path.cwd()).resolve()
    for q in [p, *p.parents]:
        if (q / MARK).exists(): return q
    raise SystemExit(f'案件フォルダが見つかりません（{MARK} が無い）。`pv.py init <フォルダ>` で作るか、案件の中で実行してください')


class Project:
    def __init__(self, root=None):
        self.root = find_root(root)
        self.cfg = json.load(open(self.root / MARK))
        self.build = self.root / 'build'
        self.harvest = self.root / 'harvest'
        self.research = self.root / 'research'
        self.assets = self.root / 'assets'
        self.exports = self.root / 'exports'
        self.src = self.build / 'src'
        self._tl = self._segs = self._fr = None

    @property
    def lang(self): return self.cfg.get('lang', 'ja')

    @property
    def name(self): return self.cfg.get('name', 'pv')

    def style(self):
        d = dict(fps=30, letterbox=True, accent='#ffd400', loudness=-14,
                 font_caption='HiraginoSans-W6', font_name='HiraginoSans-W8', font_role='AvenirNext-Bold',
                 caption_size=40, name_pos=[120, 790], vignette=45, version='v1')
        if env.is_win(): d.update(font_caption='YuGothic-Bold', font_name='YuGothic-Bold', font_role='Arial-BoldMT')
        d.update(self.jload('style.json', {}))
        return d

    def out_name(self): return f"{self.name}_{self.style()['version']}"

    def jload(self, name, default=None):
        p = self.build / name
        if not p.exists():
            if default is not None: return default
            raise SystemExit(f'{p} がありません')
        return json.load(open(p))

    def jsave(self, name, data):
        json.dump(data, open(self.build / name, 'w'), ensure_ascii=False, indent=1)

    @property
    def tl(self):
        if self._tl is None: self._tl = self.jload('timeline.json')
        return self._tl

    @property
    def segs(self):
        if self._segs is None: self._segs = self.jload('segments.json')
        return self._segs

    def blocks(self): return {b['k']: b for b in self.tl['blocks']}

    def seg_for(self, vid, a, b):
        for v, sa, sb in self.segs:
            if v == vid and sa <= a + 1e-3 and b <= sb + 1e-3: return f'{v}_{sa:.2f}_{sb:.2f}', sa
        raise SystemExit(f'取得した区間の外です {vid} {a:.2f}-{b:.2f}（edl.py を直したら `pv.py timeline` と `pv.py fetch` をやり直す）')

    def shots(self):
        """動画の絵だけを (キー, 絵) で返す。キーは「ブロック#ブロック内の番号」"""
        n, out = {}, []
        for p in self.tl['pics']:
            if 'fxk' in p: continue
            i = n.get(p['blk'], 0); n[p['blk']] = i + 1
            out.append((f"{p['blk']}#{i}", p))
        return out

    def framing(self, key, p):
        if self._fr is None: self._fr = self.jload('framing.json', {})
        FR = self._fr
        if key in FR: return FR[key]
        if p['vid'] in FR: return FR[p['vid']]
        return FR.get('_既定', [1.25, -20, 0])

    def source(self, p, pre=0.0, post=0.0):
        """絵の素材ファイルと、そのファイル内での開始秒"""
        dur = p['t1'] - p['t0']
        name, sa = self.seg_for(p['vid'], p['src'] - pre, p['src'] + dur + post)
        return self.src / f'{name}.mov', p['src'] - sa

    def window(self):
        """見える範囲の半分の幅・高さ（中心からの px）。黒帯（2.39:1）があれば上下が狭い"""
        return (960, 402) if self.style().get('letterbox', True) else (960, 540)


def grab(src, t, out, vf=None):
    cmd = [env.ffmpeg(), '-v', 'error', '-y', '-ss', f'{max(0, t):.3f}', '-i', str(src), '-frames:v', '1']
    if vf: cmd += ['-vf', vf]
    subprocess.run(cmd + [str(out)], check=True)


def probe_dur(path):
    r = subprocess.run([env.ffprobe(), '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', str(path)], capture_output=True, text=True)
    try: return float(r.stdout.strip())
    except ValueError: return 0.0
