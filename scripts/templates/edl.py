"""PV の設計図。`pv.py timeline` で実行すると build/timeline.json（全工程が読む時刻表）と build/segments.json（取得する区間）を書く。
書き換えるのは「===== ここから =====」の間だけ。時間の考え方：
- ブロックは上から順に並ぶ。ブロックの開始時刻 T ＝ 直前のブロックの終わり＋gap（負の gap で前に重ねられる）
- line … 発言。声は T から a〜b 秒（元動画の秒）を流す。shots の時刻は「声の始まりを 0 とした秒」
    ('s', 始, 終[, 見た目])            同じ動画の同じ時刻（口と声が合う）
    ('b', 動画ID, 元の秒, 始, 終[, 見た目])  差し込み（B ロール）。話している本人の顔を出すときは使わない（口がずれる）
    見た目: '' 普通 / 'night' 夜の色（色を落として青く沈める）
- fx … ブラウザで描く場面（題字・数字・地図・一覧・壁・声・X・終わり など）。中身は build/scenes.json の同じキー
- ai … AI で作った動画・フリー素材の動画などの完成素材を置く（file は案件フォルダからの道）。使い始めの秒・ゆっくり寄る・枠に入れる・溶けて入る
- over … 直前のブロックの上に、透明の場面（scenes.json で "overlay": true）を重ねる。時間は進めない（映像の上の文字・額・エンドロール）
- montage … montage_pick.json の絵を数コマずつ連打する（締めの前など）
"""
import json
from pathlib import Path

HERE = Path(__file__).parent
FPS = 30
B = []


def line(k, who, vid, a, b, sub='', shots=None, gap=.3, dip=False, look='', names=(), big=None, bigt=None, bige=None, punch=False, hard=False, layout=None):
    """k: ブロック名（英数字・一意） who: 話者 vid: YouTube の動画ID a, b: 元動画の秒（発言の始まりと終わり）
    sub: 字幕。話した言葉に近い形の区切りのリスト（1 区切り＝1 画面・1 行・句読点なし）。強調（big）と同じ言葉は入れない
    gap: 前のブロックとの間（秒） dip: True なら前との間を黒に落とす（場面の区切り）
    names: [(名前, 肩書, 出る秒, 消える秒)]（声の始まりからの秒）
    big: 強調テロップ（縦書き）。[(文字, 'white'|'pink'|'red'|'ybox'), ...] を右の列から順に。文字列なら改行で列に分ける
    bigt: 強調が出る秒（声の始まりから） bige: 消える秒（省くとブロックの終わり）
    punch: 強調の瞬間に話者の顔へ寄る（True か dict(z=1.25, land=[960, 520], face='largest'|'left'|'right'|'center')）。2 人以上映る絵では face で話者を指す
    hard: 声の頭が元動画の編集点ちょうどで、前を溶かすと別のカットが混ざるとき True（溶かさずに切る）
    layout: 強調の列の置き方を手で決めるとき [dict(text, style, size, x, y, from_='R'|'L', at), ...]"""
    if shots is None: shots = [('s', -.1, round(b - a + .25, 2))]
    B.append(dict(t='line', k=k, who=who, vid=vid, a=a, b=b, sub=[sub] if isinstance(sub, str) and sub else list(sub or []), shots=shots,
                  gap=gap, dip=dip, look=look, names=[list(x) for x in names], big=big, bigt=bigt, bige=bige, punch=punch, hard=hard, layout=layout))


def fx(k, dur, gap=0., dip=False, voice=None, voice_at=0., sub=()):
    """k: 場面の名前（build/scenes.json のキー） dur: 長さ（秒）
    voice: 場面の上に流す発言 (動画ID, a, b)。voice_at: 場面の始まりから何秒で声を出すか。sub: その字幕"""
    d = dict(t='fx', k=k, dur=dur, gap=gap, dip=dip)
    if voice: d.update(voice=list(voice), voice_at=voice_at, sub=[sub] if isinstance(sub, str) else list(sub))
    B.append(d)


def ai(k, file, dur, gap=0., dip=False, src=0., zoom=None, box=None, fade=0., fout=0., shift=None, matte=None):
    """src: 素材の何秒目から使うか zoom: (始まりの倍率, 終わりの倍率) 例 (1.0, 1.05) でゆっくり寄る
    box: [x, y, 幅, 高さ] の枠に収める（はみ出しは切る。省くと全画面） fade: 溶けて入る秒（負の gap で前の映像と重ねるとディゾルブ） fout: 黒へ溶けて消える秒
    shift: [右へ px, 下へ px] 枠の中で絵をずらす（顔が黒帯で切れるときに下げる。zoom を少し上げて余白を作る）
    matte: 透明の場面の名前。その場面の文字や形の中だけに映像を見せる（巨大な名前の中に本人の映像など。場面は over() で同じ時間に置く。box とは同時に使えない）"""
    B.append(dict(t='fx', k=k, dur=dur, gap=gap, dip=dip, kind='ai', file=file, src=src, zoom=list(zoom) if zoom else None,
                  box=list(box) if box else None, fade=fade, fout=fout, shift=list(shift) if shift else None, matte=matte))


def over(k, dur, at=0.):
    """直前のブロック（over 以外）の始まりから at 秒後に、透明の場面 k を dur 秒重ねる。時間は進めない"""
    B.append(dict(t='fx', k=k, dur=dur, gap=0., dip=False, over=True, at=at))


def montage(k='mont', gap=0.):
    p = HERE / 'montage_pick.json'
    clips = json.load(open(p)) if p.exists() else []   # [{"vid":..., "t": 元の秒, "f": コマ数}, ...]
    B.append(dict(t='fx', k=k, dur=round(sum(c['f'] for c in clips) / FPS, 3) if clips else 6.0, gap=gap, dip=False, kind='montage', clips=clips))


# ===== ここから（例。案件ごとに書き換える） =====
NAME = ('山田 太郎', 'OWNER — EXAMPLE')
# 1 痛み（夜の色・間をとる）
line('A01', '山田', 'XXXXXXXXXXX', 120.40, 125.10, ['一人で作業していると', 'この時間に起きてるのは 自分だけかもって'],
     [('b', 'YYYYYYYYYYY', 300.0, -1.2, 2.0, 'night'), ('s', 2.0, 4.9, 'night')], gap=1.2, dip=True, names=[NAME + (.4, 3.4)])
# 2 転機（強調の縦書き＋寄り）
line('A02', '山田', 'XXXXXXXXXXX', 410.00, 415.80, ['だから言いたいのは'], gap=.6, dip=True,
     big=[('画面を閉じて', 'white'), ('外に出よう', 'pink')], bigt=2.4, punch=True)
fx('title', 5.0)
# 3 中身・声・締め … montage() → fx('end', 6.5)
fx('end', 6.5)
# ===== ここまで =====

# ---- 時刻を確定（ここから下は触らない）
T = 0.0; out = []
for blk in B:
    if blk.get('over'):                                     # 重ねる場面：直前のブロックの始まりから数え、時間は進めない
        base = next(o for o in reversed(out) if not o.get('over'))
        o = dict(blk); o['T'] = round(base['T'] + blk['at'], 3); o['end'] = round(o['T'] + blk['dur'], 3)
        out.append(o); continue
    T += blk['gap']
    o = dict(blk); o['T'] = round(T, 3)
    if blk['t'] == 'line':
        dur = blk['b'] - blk['a']; sh = []
        for s in blk['shots']:
            if s[0] == 's':
                st, en = s[1], s[2]; tag = s[3] if len(s) > 3 else blk['look']
                sh.append(dict(vid=blk['vid'], src=round(blk['a'] + st, 3), t0=round(T + st, 3), t1=round(T + en, 3), sync=True, look=tag))
            else:
                _, vid, sin, st, en = s[:5]; tag = s[5] if len(s) > 5 else blk['look']
                sh.append(dict(vid=vid, src=sin, t0=round(T + st, 3), t1=round(T + en, 3), sync=False, look=tag))
        o['shots'] = sh
        o['voice'] = dict(vid=blk['vid'], a=blk['a'], b=blk['b'], t0=round(T, 3), t1=round(T + dur, 3))
        o['names'] = [dict(name=x[0], role=x[1], t0=round(T + x[2], 3), t1=round(T + x[3], 3)) for x in blk['names']]
        end = max([dur] + [s[2] if s[0] == 's' else s[4] for s in blk['shots']])
        o['end'] = round(T + end, 3); T += end
    else:
        if blk.get('voice'):
            v = blk['voice']; o['voice'] = dict(vid=v[0], a=v[1], b=v[2], t0=round(T + blk['voice_at'], 3), t1=round(T + blk['voice_at'] + v[2] - v[1], 3))
        o['end'] = round(T + blk['dur'], 3); T += blk['dur']
    out.append(o)
pics = []
for o in out:
    if o['t'] == 'line':
        for i, s in enumerate(o['shots']): pics.append(dict(s, blk=o['k'], first=(i == 0), dip=o['dip'] and i == 0, hard=o['hard'] and i == 0))
    elif o.get('kind') == 'montage':
        t = o['T']                                       # 連打は溶かさずに切る（look='cut'）
        for i, c in enumerate(o['clips']):
            pics.append(dict(vid=c['vid'], src=c['t'], t0=round(t, 3), t1=round(t + c['f'] / FPS, 3), sync=False, look='cut', blk=o['k'], first=(i == 0), dip=False, hard=True))
            t += c['f'] / FPS
    elif not o.get('over'):
        pics.append(dict(fxk=o['k'], t0=o['T'], t1=o['end'], blk=o['k'], first=True, dip=o['dip']))
pics.sort(key=lambda p: p['t0'])
for a_, b_ in zip(pics, pics[1:]):                         # 重なりは後ろ優先、隙間は前の絵を延ばす（暗転 dip のときだけ黒を残す）
    if b_['t0'] < a_['t1']: a_['t1'] = b_['t0']
    elif not b_['dip'] and b_['t0'] > a_['t1']: a_['t1'] = b_['t0']
for p in pics:
    p['t0'] = round(p['t0'], 3); p['t1'] = round(p['t1'], 3)
    if p['t1'] - p['t0'] < .3 and p.get('look') != 'cut': print('短すぎる絵', p.get('blk'), p['t0'], p['t1'])
total = round(max(o['end'] for o in out) + .2, 2)
json.dump(dict(fps=FPS, total=total, blocks=out, pics=pics), open(HERE / 'timeline.json', 'w'), ensure_ascii=False, indent=1)
for o in out:
    big = o.get('big'); big = ' '.join(b[0] if isinstance(b, (list, tuple)) else b for b in big) if isinstance(big, list) else (big or '').replace('\n', ' ')
    print(f"{o['T']:7.2f}-{o['end']:7.2f} {o['t']:4} {o['k']:7} {o.get('who', '') or o.get('kind', '')}  {' / '.join(o.get('sub') or [])}  {'★' + big if big else ''}")
print('total', total, '秒')
need = {}                                                   # 取得する区間（動画ごとに前後を広げて結合）
for o in out:
    for s in o.get('shots', []): need.setdefault(s['vid'], []).append((max(0.0, s['src'] - 1.0), s['src'] + (s['t1'] - s['t0']) + 1.0))
    if o.get('voice'):
        v = o['voice']; need.setdefault(v['vid'], []).append((max(0.0, v['a'] - 1.6), v['b'] + 1.6))
    for c in o.get('clips', []): need.setdefault(c['vid'], []).append((max(0.0, c['t'] - .6), c['t'] + c['f'] / FPS + .6))
segs = []
for vid, rs in need.items():
    rs.sort(); cur = list(rs[0])
    for a, b in rs[1:]:
        if a <= cur[1] + 2: cur[1] = max(cur[1], b)
        else: segs.append((vid, round(cur[0], 2), round(cur[1], 2))); cur = [a, b]
    segs.append((vid, round(cur[0], 2), round(cur[1], 2)))
json.dump(segs, open(HERE / 'segments.json', 'w'), indent=1)
print(len(segs), '区間', round(sum(b - a for _, a, b in segs), 1), '秒を取得')
