"""道具の場所を見つける（ffmpeg・Chrome・After Effects・顔検出）と、環境の点検（doctor）。"""
import glob, importlib.util, os, platform, shutil, subprocess, sys
from pathlib import Path

KIT = Path(__file__).resolve().parent.parent          # scripts/
RENDER = KIT / 'render'
CACHE = Path(os.environ.get('PV_CACHE', Path.home() / '.cache' / 'channel-pv-maker'))


def is_mac(): return platform.system() == 'Darwin'
def is_win(): return platform.system() == 'Windows'
def apple_silicon(): return is_mac() and platform.machine() == 'arm64'


def _first(*cands):
    for c in cands:
        if c and Path(c).exists(): return str(c)
    return None


def ffmpeg():
    # Homebrew の ffmpeg を優先（~/.local/bin などに Intel 版が混ざっている Mac がある）
    return _first(os.environ.get('PV_FFMPEG'), '/opt/homebrew/bin/ffmpeg', '/usr/local/bin/ffmpeg', shutil.which('ffmpeg')) or 'ffmpeg'


def ffprobe():
    return _first(os.environ.get('PV_FFPROBE'), '/opt/homebrew/bin/ffprobe', '/usr/local/bin/ffprobe', shutil.which('ffprobe')) or 'ffprobe'


def ytdlp(): return shutil.which('yt-dlp') or 'yt-dlp'
def node(): return shutil.which('node')


def chrome():
    """ブラウザ描画に使う Chrome。PV_CHROME → Playwright の Chromium → 普通の Chrome の順"""
    c = os.environ.get('PV_CHROME')
    if c and Path(c).exists(): return c
    pats = [str(Path.home() / 'Library/Caches/ms-playwright/chromium-*/chrome-mac*/*.app/Contents/MacOS/*'),
            str(Path.home() / '.cache/ms-playwright/chromium-*/chrome-linux*/chrome'),
            str(Path.home() / 'AppData/Local/ms-playwright/chromium-*/chrome-win*/chrome.exe')]
    for p in pats:
        hits = [h for h in sorted(glob.glob(p)) if 'Helper' not in h and Path(h).is_file()]
        if hits: return hits[-1]
    return _first('/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
                  r'C:\Program Files\Google\Chrome\Application\chrome.exe', shutil.which('google-chrome'), shutil.which('chromium'))


def ae_app():
    """入っている After Effects のうち一番新しいもの。Mac はアプリ名（osascript 用）、Windows は AfterFX.com のパス"""
    if os.environ.get('PV_AE'): return os.environ['PV_AE']
    if is_mac():
        apps = sorted(glob.glob('/Applications/Adobe After Effects 20*/Adobe After Effects 20*.app'))
        return Path(apps[-1]).stem if apps else None
    if is_win():
        hits = sorted(glob.glob(r'C:\Program Files\Adobe\Adobe After Effects 20*\Support Files\AfterFX.com'))
        return hits[-1] if hits else None
    return None


def faces_bin():
    """顔の枠を返す道具。Mac は Apple Vision（同梱の faces.swift をその場で作る）。作れなければ None（OpenCV を使う）"""
    if not is_mac(): return None
    out = CACHE / 'faces'
    if out.exists(): return str(out)
    swiftc = shutil.which('swiftc')
    if not swiftc: return None
    CACHE.mkdir(parents=True, exist_ok=True)
    r = subprocess.run([swiftc, '-O', str(KIT / 'tools' / 'faces.swift'), '-o', str(out)], capture_output=True, text=True)
    return str(out) if r.returncode == 0 and out.exists() else None


def has_module(name):
    try: return importlib.util.find_spec(name) is not None
    except Exception: return False


def ffmpeg_has(filter_name):
    r = subprocess.run([ffmpeg(), '-hide_banner', '-filters'], capture_output=True, text=True)
    return any(len(l.split()) > 1 and l.split()[1] == filter_name for l in r.stdout.splitlines())


def aac():
    """書き出しの音の変換器。Mac の aac_at は山の持ち上がりが小さい（-2dB の音が ffmpeg の aac で +0.2、aac_at で -1.7 になった）"""
    r = subprocess.run([ffmpeg(), '-hide_banner', '-encoders'], capture_output=True, text=True)
    return 'aac_at' if any(len(l.split()) > 1 and l.split()[1] == 'aac_at' for l in r.stdout.splitlines()) else 'aac'


def playwright_ready(): return (RENDER / 'node_modules' / 'playwright-core').exists()


def doctor():
    rows = []
    def row(name, ok, note=''): rows.append((name, ok, note))
    row('python3（3.9 以上）', sys.version_info >= (3, 9), sys.version.split()[0])
    for exe, label in ((ffmpeg(), 'ffmpeg'), (ffprobe(), 'ffprobe'), (ytdlp(), 'yt-dlp')):
        row(label, bool(shutil.which(exe) or Path(exe).exists()), exe)
    row('node', bool(node()), node() or 'https://nodejs.org')
    row('playwright-core（render/node_modules）', playwright_ready(), f'cd "{RENDER}" && npm install')
    row('Chrome（ブラウザ描画）', bool(chrome()), chrome() or 'Google Chrome を入れるか `npx playwright install chromium`')
    for m in ('numpy', 'PIL'): row(f'python: {m}', has_module(m), 'pip install -r requirements.txt')
    asr = next((m for m in ('mlx_whisper', 'faster_whisper', 'whisper') if has_module(m)), None)
    row('文字起こし', bool(asr), asr or 'Apple Silicon は pip install mlx-whisper、それ以外は pip install faster-whisper')
    row('声の分離（demucs）', has_module('demucs'), 'pip install demucs（無いと元動画の BGM が声の下に残る）')
    fb = faces_bin()
    row('顔検出', bool(fb) or has_module('cv2'), fb or ('OpenCV' if has_module('cv2') else 'Mac は xcode-select --install、他は pip install opencv-python'))
    ae = ae_app()
    row('After Effects', bool(ae), ae or '無し → pv.py compose（ffmpeg）で書き出す')
    w = max(len(r[0]) for r in rows)
    for name, ok, note in rows: print(f"{'OK' if ok else '--'}  {name.ljust(w)}  {note}")
    need = [r[0] for r in rows[:9] if not r[1]]
    print('\n必須が欠けています: ' + '、'.join(need) if need else '\n必須はそろっています')
    return not need
