#!/usr/bin/env python3
"""channel-pv-maker の道具。案件フォルダ（pv.project.json がある所）の中で実行する。
動きの名前:  motion <言葉> で候補、motion <番号> で AI への頼み方（どの段でも使える。案件フォルダの外でも動く）
順番:  doctor → init → harvest → sheets → （発言を選ぶ・構成を決める）→ edl.py を書く → timeline → fetch → voices → words → transcripts
       → edges / faces / crops（点検して edl.py・framing.json を直す）→ plan → scenes → telops → mix → ae build → ae render（AE が無ければ compose）→ qa → preview
"""
import argparse, json, shutil, subprocess, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from pvkit import env  # noqa: E402

TPL = Path(__file__).resolve().parent / 'templates'


def P():
    from pvkit.project import Project
    return Project()


def cmd_init(a):
    root = Path(a.dir).expanduser().resolve()
    if (root / 'pv.project.json').exists(): print('すでに案件フォルダです', root); return
    for d in ('research', 'harvest', 'assets/brand', 'assets/thumbs', 'assets/x', 'assets/banners', 'assets/music', 'assets/sfx', 'assets/ai', 'planning', 'build', 'exports', 'ae'):
        (root / d).mkdir(parents=True, exist_ok=True)
    name = a.name or root.name
    json.dump(dict(name=name, lang=a.lang, channel=a.channel or ''), open(root / 'pv.project.json', 'w'), ensure_ascii=False, indent=1)
    for f in ('edl.py', 'style.json', 'scenes.json', 'audio.json', 'framing.json', 'montage_pick.json'):
        if not (root / 'build' / f).exists(): shutil.copy(TPL / f, root / 'build' / f)
    if not (root / 'planning' / 'plan.md').exists(): shutil.copy(TPL / 'plan.md', root / 'planning' / 'plan.md')
    print('案件フォルダを作りました →', root)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sp = ap.add_subparsers(dest='cmd', required=True)
    sp.add_parser('doctor', help='道具がそろっているか点検する')
    s = sp.add_parser('motion', help='動きの名前を言葉から探す（Motion Prompt 144 件）・番号で頼み方を出す'); s.add_argument('words', nargs='*'); s.add_argument('--list', choices=['motion', 'camera', 'ui', 'lp', 'photo', 'motion2'])
    s = sp.add_parser('init', help='案件フォルダを作る'); s.add_argument('dir'); s.add_argument('--name'); s.add_argument('--lang', default='ja'); s.add_argument('--channel')
    s = sp.add_parser('harvest', help='チャンネルか動画のリンクから素材を集める'); s.add_argument('urls', nargs='+'); s.add_argument('--limit', type=int, default=0)
    s.add_argument('--min-dur', type=float, default=60); s.add_argument('--no-asr', action='store_true')
    s = sp.add_parser('sheets', help='下見の一覧画像'); s.add_argument('vids', nargs='*'); s.add_argument('--every', type=float, default=10)
    s = sp.add_parser('frames', help='指定の秒のコマ'); s.add_argument('vid'); s.add_argument('times')
    s = sp.add_parser('xshot', help='X の投稿の画像（ID か URL を 1 行ずつ書いたファイル）'); s.add_argument('ids_file')
    s = sp.add_parser('map', help='地図の場面の輪郭と地点'); s.add_argument('--places', nargs='+', required=True); s.add_argument('--geojson')
    for c, h in (('timeline', 'edl.py を実行して時刻表を作る'), ('fetch', '本番素材（1080p）を取る'), ('voices', '声だけを抜き出す'), ('words', '語尾の位置を測る'),
                 ('transcripts', '発言を高精度で起こす（字幕の切り替え用）'), ('prep', 'timeline→fetch→voices→words→transcripts をまとめて'),
                 ('edges', '元動画の編集点の切れ端を探す'), ('plan', '組み立ての中身（_comp.json）を作る'), ('mix', '音を作る')):
        sp.add_parser(c, help=h)
    s = sp.add_parser('faces', help='顔が黒帯で切れないか'); s.add_argument('--apply', action='store_true')
    s = sp.add_parser('crops', help='完成時に見える絵を並べる'); s.add_argument('keys', nargs='*')
    s = sp.add_parser('scenes', help='場面を描いて書き出す'); s.add_argument('keys', nargs='*')
    s = sp.add_parser('telops', help='強調テロップを描いて書き出す'); s.add_argument('keys', nargs='*')
    s = sp.add_parser('still', help='場面か強調を 1 コマだけ描く'); s.add_argument('what', choices=['scenes', 'telops']); s.add_argument('key'); s.add_argument('times')
    s = sp.add_parser('ae', help='After Effects で組み立てる（build）・書き出す（render）'); s.add_argument('step', choices=['build', 'render']); s.add_argument('--keep-mov', action='store_true')
    s = sp.add_parser('compose', help='AE 無しで書き出す（ffmpeg）'); s.add_argument('--keep', action='store_true')
    s = sp.add_parser('qa', help='書き出した動画を検品する'); s.add_argument('--video'); s.add_argument('--no-asr', action='store_true')
    s = sp.add_parser('preview', help='スマホで見られる軽い確認版'); s.add_argument('--mb', type=float, default=27)
    a = ap.parse_args()

    if a.cmd == 'doctor': sys.exit(0 if env.doctor() else 1)
    if a.cmd == 'init': return cmd_init(a)
    if a.cmd == 'motion':
        from pvkit import motion
        sys.exit(motion.main(a.words, a.list))
    p = P()
    if a.cmd == 'harvest':
        from pvkit import harvest; harvest.run(p, a.urls, a.limit, a.min_dur, no_asr=a.no_asr)
    elif a.cmd == 'sheets':
        from pvkit import sheets; sheets.sheets(p, a.vids, a.every)
    elif a.cmd == 'frames':
        from pvkit import sheets; sheets.frames(p, a.vid, [float(x) for x in a.times.split(',')])
    elif a.cmd == 'xshot':
        from pvkit import render
        e = dict(**__import__('os').environ); c = env.chrome()
        if c: e['PV_CHROME'] = c
        if not env.playwright_ready(): subprocess.run(['npm', 'install', '--silent'], cwd=env.RENDER, check=True)
        subprocess.run([env.node(), str(env.RENDER / 'xshot.mjs'), str(p.root), str(Path(a.ids_file).resolve())], check=True, env=e)
    elif a.cmd == 'map':
        from pvkit import mapdata; mapdata.build(p, a.places, a.geojson)
    elif a.cmd in ('timeline', 'prep'):
        subprocess.run([sys.executable, 'edl.py'], cwd=p.build, check=True)
        if a.cmd == 'prep':
            from pvkit import media
            p = P(); media.fetch(p); media.voices(p); media.words(p); media.transcripts(p)
    elif a.cmd in ('fetch', 'voices', 'words', 'transcripts'):
        from pvkit import media; getattr(media, a.cmd)(p)
    elif a.cmd == 'edges':
        from pvkit import checks; checks.edges(p)
    elif a.cmd == 'faces':
        from pvkit import checks; checks.faces(p, a.apply)
    elif a.cmd == 'crops':
        from pvkit import checks; checks.crops(p, a.keys or None)
    elif a.cmd == 'plan':
        from pvkit import plan; plan.build(p)
    elif a.cmd == 'scenes':
        from pvkit import render; render.scenes(p, a.keys or None)
    elif a.cmd == 'telops':
        from pvkit import render; render.telops(p, a.keys or None)
    elif a.cmd == 'still':
        from pvkit import render; render.still(p, a.what, a.key, a.times)
    elif a.cmd == 'mix':
        from pvkit import mix; mix.run(p)
    elif a.cmd == 'ae':
        from pvkit import ae
        ae.build(p) if a.step == 'build' else ae.render(p, a.keep_mov)
    elif a.cmd == 'compose':
        from pvkit import compose; compose.run(p, a.keep)
    elif a.cmd == 'qa':
        from pvkit import qa; qa.run(p, a.video, a.no_asr)
    elif a.cmd == 'preview':
        from pvkit import qa; qa.preview(p, mb=a.mb)


if __name__ == '__main__':
    main()
