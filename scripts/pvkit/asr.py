"""文字起こし（語の時刻つき）。mlx-whisper（Apple Silicon）→ faster-whisper → openai-whisper の順に使えるものを使う。
返り値は {text, segments: [{start, end, text, words: [{start, end, word}]}]} にそろえる。"""
import numpy as np
from .env import has_module

MODELS = {
    'mlx_whisper': {'fast': 'mlx-community/whisper-large-v3-turbo', 'best': 'mlx-community/whisper-large-v3-mlx'},
    'faster_whisper': {'fast': 'large-v3-turbo', 'best': 'large-v3'},
    'whisper': {'fast': 'turbo', 'best': 'large-v3'},
}
_cache = {}


def engine():
    for m in ('mlx_whisper', 'faster_whisper', 'whisper'):
        if has_module(m): return m
    raise SystemExit('文字起こしの道具がありません。Apple Silicon は `pip install mlx-whisper`、それ以外は `pip install faster-whisper`')


def _norm(segs):
    out = [{'start': s['start'], 'end': s['end'], 'text': s['text'],
            'words': [{'start': w['start'], 'end': w['end'], 'word': w['word']} for w in (s.get('words') or [])]} for s in segs]
    return {'text': ''.join(s['text'] for s in out), 'segments': out}


def transcribe(audio, lang='ja', quality='fast'):
    """audio: ファイルのパスか 16kHz モノラルの float32 配列。quality: fast（turbo）か best（large-v3）"""
    e = engine(); name = MODELS[e][quality]
    a = audio if isinstance(audio, str) else np.asarray(audio, np.float32)
    if e == 'mlx_whisper':
        import mlx_whisper
        return _norm(mlx_whisper.transcribe(a, path_or_hf_repo=name, language=lang, word_timestamps=True)['segments'])
    if e == 'faster_whisper':
        from faster_whisper import WhisperModel
        if name not in _cache:
            try: _cache[name] = WhisperModel(name, compute_type='int8')
            except Exception: _cache[name] = WhisperModel('large-v3', compute_type='int8')
        segs, _ = _cache[name].transcribe(a, language=lang, word_timestamps=True)
        return _norm([{'start': s.start, 'end': s.end, 'text': s.text,
                       'words': [{'start': w.start, 'end': w.end, 'word': w.word} for w in (s.words or [])]} for s in segs])
    import whisper
    if name not in _cache: _cache[name] = whisper.load_model(name)
    return _norm(_cache[name].transcribe(a, language=lang, word_timestamps=True)['segments'])


def words(result):
    return [[round(w['start'], 2), round(w['end'], 2), w['word']] for s in result['segments'] for w in s.get('words', [])]
