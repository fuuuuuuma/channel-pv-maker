# 命令の順番と設計図（edl.py）の書き方

`python3 "$PV" <命令>`。案件フォルダの中で実行する。

| 段 | 命令 | できるもの | 見ること |
|---|---|---|---|
| 準備 | `doctor` | 点検の表 | 必須の欠け |
| | `init <フォルダ> --name <英数字の名前>` | 案件フォルダと雛形（build/edl.py・style.json・scenes.json・audio.json・framing.json） | |
| 下調べ | `harvest <チャンネル URL か動画 URL...> --limit 15` | research/videos.tsv・harvest/<ID>/（下見・音声・文字起こし・概要欄）・assets/thumbs・assets/brand | 失敗した動画 |
| | `sheets [ID...] --every 10` | research/sheets/<ID>_n.jpg（10 秒ごとのコマ 30 枚） | 使える絵・焼き込みの位置 |
| | `frames <ID> 120.5,300` | research/frames/ | 1 コマを原寸で |
| | `xshot ids.txt` | assets/x/<投稿ID>.png | 取れなかった投稿 |
| | `map --places 東京=139.69,35.69 大阪=135.50,34.69` | build/map.json（日本の都道府県の輪郭） | |
| 素材 | `prep`（＝ timeline → fetch → voices → words → transcripts） | build/timeline.json・segments.json・src/・voc/・words.json・transcripts.json | 「短すぎる絵」の表示・取得の失敗 |
| 点検 | `edges` | 編集点の切れ端の一覧 | 全部直す |
| | `faces --apply` | framing.json に顔が切れない位置 | 上下とも切れるものは倍率を下げて手で |
| | `crops [キー...]` | build/_frames/crop_*.jpg | 焼き込み・顔・構図 |
| 組み立て | `plan` | build/_comp.json | 寄りの先の顔・字幕の区切り |
| | `scenes [名前...]` / `still scenes <名前> 1,3` | build/fx/<名前>.mov | 1 コマで先に見る |
| | `telops` / `still telops <キー> 1.5` | build/telop/<キー>.mov | 顔に重ならないか |
| | `mix` | build/mix.wav・stems/ | 語尾の伸ばしの一覧 |
| 書き出し | `ae build` → `ae render` | ae/<名前>.aep・build/_ae_check/sheet.jpg・exports/<名前>.mp4 | sheet.jpg を必ず見る |
| | `compose`（AE が無いとき） | exports/<名前>.mp4・build/_ff_check/sheet.jpg | |
| 検品 | `qa` / `preview` | build/_qa/・exports/<名前>_preview.mp4 | `qa.md` |

edl.py・framing.json・scenes.json・audio.json を直したら、影響する所からやり直す：
edl.py → `prep` 以降すべて／framing.json → `plan` 以降／scenes.json → `scenes` 以降／audio.json → `mix` 以降。

## 設計図（build/edl.py）

「===== ここから ===== 〜 ===== ここまで =====」だけを書き換える。上から順に時間が流れる。

```python
OWNER = ('山田 太郎', 'OWNER — EXAMPLE')                     # (名前, 英字の肩書)。肩書が分からなければ ''
# 1 痛み（夜の色・余白）
line('A01', 'メンバー', 'VIDEO_ID_1', 1435.00, 1440.88, ['でも都会の中で パソコンの前で', 'キーボード叩いて', 'モニターと睨めっこして'],
     [('b', 'VIDEO_ID_2', 2658.9, -1.4, 2.7, 'night'), ('b', 'VIDEO_ID_3', 754.7, 2.7, 6.3, 'night')], gap=1.4, dip=True)
line('A03', '山田', 'VIDEO_ID_4', 1567.08, 1572.52, ['僕の場合はやっぱり 1人でやってて', 'すごく病んだし', 'ストレートに言うと 寂しかったですね'],
     [('s', -.1, 5.8, 'night')], gap=1.0, dip=True, names=[OWNER + (.5, 3.6)])
ai('tear', 'assets/ai/tear.mp4', 5.0, gap=.5)                 # 任意：AI で作った転機の演出
line('A05', '山田', 'VIDEO_ID_5', 657.52, 663.32, ['〇〇って 何回も言ってるけど'], gap=0,
     big=[('画面を', 'white'), ('オフにして', 'white'), ('外に出よう', 'pink')], bigt=3.0, bige=6.3)
fx('title', 5.0)
line('B06', '山田', 'VIDEO_ID_6', 493.53, 496.90, ['我々の理念'], [('b', 'VIDEO_ID_5', 1561.4, -.3, .85), ('s', .85, 3.6)], gap=-.3,
     big=[('楽しく', 'white'), ('クリエイティブで', 'white'), ('稼ぐ', 'pink')], bigt=1.1, punch=True)
fx('voices', 17.0, gap=.6, dip=True)                          # 声を文字で（映像の音は無し）
fx('xwall', 9.0, voice=('VIDEO_ID_7', 853.88, 858.12), voice_at=4.2, sub=['ここで話して すごいスッキリしたし', 'もっと頑張ろうって思いました'])
line('F22', '山田', 'VIDEO_ID_8', 3028.20, 3036.52, ['楽しさも稼ぎも 上げたい人は'], gap=.4, dip=True,
     big=[('俺が人生', 'white'), ('変える', 'red')], bigt=6.7, punch=True)   # 最後の声は主役
montage()                                                      # 高速の連打（声は無し）
fx('end', 6.5)
```

- `a`, `b`（元動画の秒）は文字起こしの語の時刻で決め、`prep` の後に出る「始め／終わりのそばの語」で確かめる。
  前の言葉が入っていたら a を後ろへ、次の言葉が入っていたら b を手前へ。語の時刻は 0.1〜0.2 秒早めに出ることがある。
- shots の時刻は「声の始まりが 0」。`('s', -.1, 5.8)` は声の 0.1 秒前から 5.8 秒まで同じ時刻の絵。差し込みの元の秒は `sheets` で選ぶ。
- 頭が元動画の編集点ちょうどで、溶かすと前の別カットが混ざるときは `hard=True`（`edges` が教える）。
- 名前の札 `names` は 1 人目に出てきたときだけ。場所の札（「東京オフ会」「TOKYO — 90 CREATORS」）にも使える。
- 強調 `big` は右の列から読む。白（white）を右の端、効かせる語（pink / red / ybox）を左の端に自動で置く。
  置き方が顔に重なるときは `layout=[dict(text, style, size, x, y, from_='R', at=0), ...]` で手で決める（x は列の左端・size は 1 文字の px）。
- 寄り `punch` は強調の瞬間に話者の顔へ 0.22 秒で寄る。2 人以上映る絵では `punch=dict(face='left')` のように話者を指す。

## 切り取り（build/framing.json）

`[倍率, 上下のずらし, 左右のずらし]`。ずらしは元画像（1920×1080）の px で、上下は正で下側を見せる。
既定 `[1.25, -20, 0]`（黒帯の内側に収め、上の焼き込みラベルと下の字幕を隠す）。キーは `ブロック#番号`（その絵だけ）か動画 ID（その動画の全部）。
`faces --apply` が顔の切れる所に案を入れる。焼き込みが残る絵は倍率を上げるか差し込みを替える。倍率 1.0 未満は使わない（黒い余白が出る）。
