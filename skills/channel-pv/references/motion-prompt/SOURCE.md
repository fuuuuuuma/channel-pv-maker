# Motion Prompt（動きの名前のライブラリ）の写し

- 元：Motion Prompt — https://showheyohtaki.github.io/motion-prompt/ ／ GitHub `showheyohtaki/motion-prompt`
- 作者：大滝昇平（Shohei Ohtaki・@showheyohtaki）
- ライセンス：MIT（このフォルダの `LICENSE` が原文。写しを配るときは LICENSE を一緒に残す）
- 写した版：commit `bd6bf08d8d412cc82c1bbc8f1a81638617a45cfb`（2026-10-23。lp2 パック #145–168 を足した版）
- 写したもの：
  - `catalog.tsv` … 日本語の一覧 168 件（列：番号・パック・カテゴリ・名前・タグ・何が起きるか）。元の `api/v1/ja/catalog.tsv`
  - `prompts/NNN.txt` … 1 件ずつの「AI への頼み方」（そのまま貼れる文・動きの仕様・使いどころ）。元の `api/v1/ja/p/NNN.txt`
- 写していないもの：動く見本のコード（Canvas 2D）。必要なときは各 `prompts/NNN.txt` の末尾の URL（参考実装・共通の補助コード）から読む。
- 番号は元のライブラリと同じ（元は公開後に番号を振り直さない決まり）。新しい版を取り込むときは、元の `api/v1/ja/` を同じ形で上書きし、この版の行を直す。

パックと番号：
| 番号 | パック | 中身 |
|---|---|---|
| 001–024 | motion | モーショングラフィックスの動き（登場・文字・味付け・切り替え） |
| 025–048 | camera | カメラワークと切り替え |
| 049–072 | ui | UI パーツの名前 |
| 073–096 | lp | LP・Web サイトの演出 |
| 097–120 | photo | 写真の表現・光と画風 |
| 121–144 | motion2 | モーショングラフィックスの演出 第2弾 |
| 145–168 | lp2 | LP・Web サイトの演出 第2弾（スクロール・マウスや入力への反応・見せ場） |
