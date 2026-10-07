"""チャンネル（または動画のリンク）から素材を集める：動画の一覧・下見（360p）・音声・概要欄・サムネ・語の時刻つき文字起こし。
出力: research/videos.tsv（ID・タイトル・秒・公開日）、harvest/<ID>/（src.mp4・audio.wav・desc.txt・transcript.json・transcript.txt）、
     assets/thumbs/<ID>.jpg、assets/brand/（チャンネルのアイコン・バナー。取れたときだけ）"""
import json, os, re, subprocess, time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from . import env, asr

YT = ['--no-update', '--extractor-args', 'youtube:player_client=web_embedded,default']


def vid_of(url):
    m = re.search(r'(?:v=|youtu\.be/|shorts/|live/)([\w-]{11})', url)
    return m.group(1) if m else (url if re.fullmatch(r'[\w-]{11}', url) else None)


def list_channel(url, limit):
    """チャンネルの「動画」タブを新しい順に。Shorts は別タブなので入らない"""
    u = url.rstrip('/')
    if not re.search(r'/(videos|streams|shorts|playlist)', u) and 'list=' not in u: u += '/videos'
    cmd = [env.ytdlp(), *YT, '--flat-playlist', '--print', '%(id)s\t%(title)s\t%(duration)s\t%(upload_date)s', u]
    if limit: cmd[1:1] = ['--playlist-end', str(limit)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    rows = [l.split('\t') for l in r.stdout.splitlines() if l.count('\t') >= 3]
    if not rows: raise SystemExit('動画の一覧が取れませんでした: ' + r.stderr.strip()[-300:])
    return rows


def meta_one(vid):
    r = subprocess.run([env.ytdlp(), *YT, '--skip-download', '--print', '%(id)s\t%(title)s\t%(duration)s\t%(upload_date)s', f'https://youtu.be/{vid}'], capture_output=True, text=True)
    p = r.stdout.strip().split('\t')
    return p if len(p) >= 4 else [vid, '', '0', '']


def channel_art(url, out):
    """チャンネルのアイコンとバナー（--playlist-items 0 でチャンネル自体のサムネだけを取る）"""
    out.mkdir(parents=True, exist_ok=True)
    subprocess.run([env.ytdlp(), *YT, '--skip-download', '--write-all-thumbnails', '--playlist-items', '0', '--convert-thumbnails', 'jpg',
                    '-o', str(out / 'channel.%(ext)s'), url.rstrip('/')], capture_output=True, text=True)


def download(vid, H, thumbs, tries=3):
    d = H / vid; d.mkdir(parents=True, exist_ok=True)
    for i in range(tries):
        if (d / 'src.mp4').exists(): break
        subprocess.run([env.ytdlp(), *YT, '-f', 'bv*[height<=360][ext=mp4]+ba[ext=m4a]/bv*[height<=480]+ba/b[height<=480]', '--merge-output-format', 'mp4',
                        '-o', str(d / 'src.%(ext)s'), f'https://youtu.be/{vid}'], capture_output=True, text=True)
        if not (d / 'src.mp4').exists(): time.sleep(8 + 6 * i)
    if not (d / 'src.mp4').exists(): return vid, 'FAIL'
    if not (d / 'audio.wav').exists():
        subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-i', str(d / 'src.mp4'), '-vn', '-ac', '1', '-ar', '16000', str(d / 'audio.wav')], check=True)
    if not (d / 'desc.txt').exists():
        r = subprocess.run([env.ytdlp(), *YT, '--skip-download', '--print', 'description', f'https://youtu.be/{vid}'], capture_output=True, text=True)
        (d / 'desc.txt').write_text(r.stdout)
    t = thumbs / f'{vid}.jpg'
    if not t.exists():
        subprocess.run([env.ytdlp(), *YT, '--skip-download', '--write-thumbnail', '--convert-thumbnails', 'jpg', '-o', str(thumbs / vid), f'https://youtu.be/{vid}'], capture_output=True)
    return vid, 'ok'


def transcribe_all(H, vids, lang):
    for vid in vids:
        d = H / vid
        if (d / 'transcript.json').exists() or not (d / 'audio.wav').exists(): continue
        r = asr.transcribe(str(d / 'audio.wav'), lang=lang)
        json.dump(r, open(d / 'transcript.json', 'w'), ensure_ascii=False)
        with open(d / 'transcript.txt', 'w') as f:
            for s in r['segments']: f.write(f"[{s['start']:.2f}-{s['end']:.2f}] {s['text'].strip()}\n")
        print('文字起こし', vid, len(r['segments']), '区切り', flush=True)


def run(P, urls, limit=0, min_dur=60, jobs=3, no_asr=False):
    rows = []
    for u in urls:
        if vid_of(u) and 'list=' not in u: rows.append(meta_one(vid_of(u)))
        else:
            rows += list_channel(u, limit)
            channel_art(u, P.assets / 'brand')
    seen, keep, short = set(), [], []
    for r in rows:
        if r[0] in seen: continue
        seen.add(r[0])
        try: dur = float(r[2])
        except ValueError: dur = 0
        if dur and dur < min_dur: short.append(r); continue   # 短すぎる動画（Shorts など）は外す
        keep.append(r)
    P.research.mkdir(exist_ok=True)
    tsv = P.research / 'videos.tsv'
    old = {l.split('\t')[0] for l in tsv.read_text().splitlines()} if tsv.exists() else set()
    with open(tsv, 'a') as f:
        for r in keep:
            if r[0] not in old: f.write('\t'.join(r[:4]) + '\n')
    print('動画', len(keep), '本 →', tsv)
    thumbs = P.assets / 'thumbs'; thumbs.mkdir(parents=True, exist_ok=True)
    failed = []
    with ThreadPoolExecutor(jobs) as ex:
        for vid, st in ex.map(lambda r: download(r[0], P.harvest, thumbs), keep):
            print('取得', vid, st, flush=True)
            if st != 'ok': failed.append(vid)
    if not no_asr: transcribe_all(P.harvest, [r[0] for r in keep if r[0] not in failed], P.lang)
    log = [f'一覧 {len(rows)} 本・使う {len(keep) - len(failed)} 本・除外 {len(short)} 本（{min_dur:.0f} 秒未満）・失敗 {len(failed)} 本 {failed}']
    for r in keep:
        tj = P.harvest / r[0] / 'transcript.json'
        if not tj.exists(): continue
        segs = json.load(open(tj))['segments']
        texts = [x['text'].strip() for x in segs if x['text'].strip()]
        rep = 1 - len(set(texts)) / max(1, len(texts))
        gaps = [(round(a['end']), round(b['start'])) for a, b in zip(segs, segs[1:]) if b['start'] - a['end'] > 30]
        talk = sum(x['end'] - x['start'] for x in segs)
        note = []
        if rep > .3: note.append(f'同じ文の繰り返しが多い（{rep:.0%}・音楽や無言の動画かも）')
        if gaps: note.append(f'30 秒以上の無言 {gaps[:5]}')
        if talk < 60: note.append(f'話している時間が短い（{talk:.0f} 秒）')
        log.append(f"{r[0]}  {r[1][:40]}  {'／'.join(note) if note else '話し声あり'}")
    (P.research / 'harvest_log.txt').write_text('\n'.join(log) + '\n')
    print('\n'.join(log))
    print('完了。research/videos.tsv・harvest_log.txt と harvest/<ID>/transcript.txt を読んで発言を選ぶ')
