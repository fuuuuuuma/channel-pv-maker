# 変更履歴

## 0.1.0（2026-10-07）
- 最初の版。チャンネルや動画のリンクから紹介 PV を作るスキル `channel-pv` と道具 `scripts/pv.py`
- 下調べ（harvest・sheets・xshot）→ 軽い質問 → 構成表 → 設計図（edl.py）→ 素材の下ごしらえ（prep）と点検（edges・faces・crops）
  → 場面と強調テロップの描画（scenes・telops）→ 音（mix）→ After Effects（ae build / render）か ffmpeg（compose）→ 検品（qa・preview）
- Mac（Apple Silicon・After Effects 2026）で AE と ffmpeg の両方の書き出しを通した
