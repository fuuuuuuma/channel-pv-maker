"""After Effects で組み立てて書き出す。
  pv.py ae build    build/_comp.json → build/_ae/build.jsx を AE で実行 → ae/<名前>.aep と確認用のコマ build/_ae_check/f_*.png
  pv.py ae render   AE のレンダーキューで ProRes に書き出し → 音（mix.wav）と合わせて exports/<名前>.mp4
Mac は osascript の DoScript（$.evalFile）で、Windows は AfterFX.com -r で台本を走らせる。
AE は同じ PC の別の作業と共用していることがある：開いているのが別のプロジェクトなら台本は何もせずに止まる（BUSY.txt）。"""
import json, os, shutil, subprocess, time
from pathlib import Path
from . import env
from .project import probe_dur

AE_DIR = env.KIT / 'ae'


def _run_jsx(path, timeout):
    app = env.ae_app()
    if not app: raise SystemExit('After Effects が見つかりません。AE 無しで書き出すなら `pv.py compose`')
    if env.is_win():
        subprocess.Popen([app, '-r', str(path)]); return
    p = str(path).replace('\\', '\\\\').replace('"', '\\"')
    script = f'$.evalFile(new File("{p}"));'.replace('\\', '\\\\').replace('"', '\\"')
    subprocess.run(['osascript', '-e', f'with timeout of {timeout} seconds', '-e', f'tell application "{app}" to DoScript "{script}"', '-e', 'end timeout'], check=False)


def build(P):
    D = P.jload('_comp.json')
    (P.root / 'ae').mkdir(exist_ok=True)
    chk = P.build / '_ae_check'; shutil.rmtree(chk, ignore_errors=True); chk.mkdir()
    D['aep'] = str(P.root / 'ae' / f"{D['name']}.aep"); D['aep_name'] = f"{D['name']}.aep"; D['checks'] = str(chk)
    out = P.build / '_ae'; out.mkdir(exist_ok=True)
    body = (AE_DIR / 'build_body.jsx').read_text().replace('// @@LIB@@', (AE_DIR / 'lib.jsx').read_text())
    (out / 'build.jsx').write_text('﻿' + 'var D = ' + json.dumps(D, ensure_ascii=False) + ';\n' + body, encoding='utf-8')
    _run_jsx(out / 'build.jsx', 1800)
    for _ in range(600):
        if (chk / 'DONE.txt').exists() or (chk / 'ERROR.txt').exists() or (chk / 'BUSY.txt').exists(): break
        time.sleep(2)
    if (chk / 'BUSY.txt').exists(): raise SystemExit('AE で別のプロジェクトが開いています（' + (chk / 'BUSY.txt').read_text().strip() + '）。保存して閉じてもらってからやり直す')
    if (chk / 'ERROR.txt').exists(): raise SystemExit((chk / 'ERROR.txt').read_text())
    if not (chk / 'DONE.txt').exists(): raise SystemExit('AE から返事がありません。AE の画面にダイアログが出ていないか見る（gotchas.md）')
    for _ in range(90):                                    # 確認用のコマは AE が後から書き出す
        if len(list(chk.glob('f_*.png'))) >= len(D['checktimes']): break
        time.sleep(2)
    sheet(chk)
    print('AE の組み立て完了 →', D['aep'], '／確認用のコマ', len(list(chk.glob('f_*.png'))), '枚 →', chk / 'sheet.jpg')


def sheet(chk):
    """確認用のコマを 1 枚の一覧にする（左上に秒）"""
    from PIL import Image, ImageDraw
    fs = sorted(chk.glob('f_*.png'))
    if not fs: return
    W, H = 640, 360; s = Image.new('RGB', (W * 3, H * ((len(fs) + 2) // 3)))
    for i, f in enumerate(fs):
        im = Image.open(f).convert('RGB').resize((W, H)); ImageDraw.Draw(im).text((8, 6), f'{int(f.stem[2:]) / 100:.2f}s', fill=(255, 0, 255))
        s.paste(im, ((i % 3) * W, (i // 3) * H))
    s.save(chk / 'sheet.jpg', quality=85)


def render(P, keep_mov=False):
    D = P.jload('_comp.json'); name = D['name']
    P.exports.mkdir(exist_ok=True)
    mov = P.exports / f'_{name}_render.mov'; log = P.build / '_ae' / 'render_log.txt'
    if mov.exists(): mov.unlink()
    if log.exists(): log.unlink()
    free = shutil.disk_usage(P.exports).free / 1e9; need = D['total'] * .018
    if free < need + 2: raise SystemExit(f'空き容量が足りません（空き {free:.0f}GB・ProRes に約 {need:.0f}GB 要る）')
    R = dict(aep_name=f'{name}.aep', comp=name, out=str(mov), log=str(log))
    js = P.build / '_ae' / 'render.jsx'
    js.write_text('﻿' + 'var R = ' + json.dumps(R, ensure_ascii=False) + ';\n' + (AE_DIR / 'render_body.jsx').read_text(), encoding='utf-8')
    _run_jsx(js, 3600 * 3)
    for _ in range(3600 * 3 // 5):
        if log.exists() and ('終了' in log.read_text() or '失敗' in log.read_text() or '別の' in log.read_text() or '無い' in log.read_text()): break
        time.sleep(5)
    print(log.read_text().strip() if log.exists() else '書き出しの記録がありません')
    if not mov.exists() or probe_dur(mov) < D['total'] - 1: raise SystemExit('書き出しが途中で止まりました（空き容量・AE のダイアログを確かめる）')
    mux(P, mov, keep_mov)


def mux(P, mov, keep_mov=False):
    D = P.jload('_comp.json'); out = P.exports / f"{D['name']}.mp4"
    subprocess.run([env.ffmpeg(), '-v', 'error', '-y', '-i', str(mov), '-i', str(P.build / 'mix.wav'), '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-preset', 'slow',
                    '-crf', '16', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k', '-movflags', '+faststart', '-shortest', str(out)], check=True)
    if not keep_mov: Path(mov).unlink(missing_ok=True)
    print('書き出し →', out, f'{probe_dur(out):.1f}秒', f'{out.stat().st_size / 1e6:.0f}MB')
