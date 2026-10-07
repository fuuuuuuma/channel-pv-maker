# 変更履歴

## 0.1.1（2026-10-07）
- 試しにスキルを使わせて見つかった所を直した：質問は 4 問まで（依頼文で分かることは聞かない）・許可と費用に「おすすめ」を付けない・誘いの行き先と募集の時期を聞く
- 下調べの結果を先に 3〜5 行で見せる。`harvest` が「使う本数・除外・失敗」と、音楽だけ・無言の動画の警告を research/harvest_log.txt に書く
- 話者の確かめ方・動画の冒頭の予告は使わない・数字は出典と日付つきで新しい方・2〜3 分の配分・AI 無しの転機の作り方を structure.md に
- 構成表の雛形（planning/plan.md）を `init` が置く。設計図の例をプレースホルダに。名前の札の肩書は空でよい。音楽が途切れる区間を `mix` が知らせる

## 0.1.0（2026-10-07）
- 最初の版。チャンネルや動画のリンクから紹介 PV を作るスキル `channel-pv` と道具 `scripts/pv.py`
- 下調べ（harvest・sheets・xshot）→ 軽い質問 → 構成表 → 設計図（edl.py）→ 素材の下ごしらえ（prep）と点検（edges・faces・crops）
  → 場面と強調テロップの描画（scenes・telops）→ 音（mix）→ After Effects（ae build / render）か ffmpeg（compose）→ 検品（qa・preview）
- Mac（Apple Silicon・After Effects 2026）で AE と ffmpeg の両方の書き出しを通した
