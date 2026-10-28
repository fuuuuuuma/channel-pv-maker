# 見た目（style.json と scenes.json）

目標は「テレビ CM・広告に出せる水準」。ブランドのロゴと色は守るが、無理にブランドの絵柄（漫画調など）へ寄せない。
派手な装飾を足すより、余白・黒・1 色の差し色・大きく強い文字で締める方が上等に見える。

## 2 つの型

**A シネマ（既定）** — `style.json`: `"letterbox": true, "accent": "#ffd400", "vignette": 45`
- 映像は上下の黒帯（2.39:1）の内側。字幕は下の黒帯の中に白文字（箱なし）。元動画の焼き込み字幕と章ラベルも黒帯と拡大で隠れる
- 場面は黒の地（scenes.json の `theme.bg`）に白と差し色。題字と終わりはロゴの画像をブランド色の地（`brand` / `brand_end`）に
- 冒頭の暗い幕は `look='night'`（色を落として青く沈める）

**B ブランド色** — `style.json`: `"letterbox": false, "vignette": 20`、scenes.json の `theme.brand` をロゴの色に
- 黒帯なし・字幕は画面の下に白文字＋影。場面の `title` を `brand` に、区切りは `chapter`
- 明るく親しみのある印象。CM 感は A より下がるので、ブランドが明るい・若い視聴者向けのときに

差し色はロゴの色から 1 色だけ取る（例 黄 #ffd400、オレンジ #f07a12）。2 色目（`accent2`）は控えめに。

## 強調テロップ（縦書き）

極太の明朝（Noto Serif JP Black。無ければヒラギノ明朝）を縦書きで画面の左右の端に大きく置く。
- `white` 白に影／`pink` `red` 赤×マゼンタのかすれ（効かせる語）／`ybox` 黄色の箱に白文字（1 文字ずつ箱）
- 入りの 0.3 秒は帯状に割れてずれた状態から定まり、消えるときも帯状にずれる。強調の間は映像を 30% 暗くし、衝撃音（audio.json の `auto.big`）
- 1 本に 4〜6 個まで。話者の顔は画面の中央に寄せ（punch）、文字は左右の端。顔に重なるなら `layout` で列を動かすか差し込みの絵を替える

## 場面の種類（scenes.json の `scenes.<名前>.type`）

画像の道は案件フォルダから（`assets/...`）。`<b>…</b>` は差し色。長さは edl.py の `fx(名前, 秒)`。

| type | 中身 | 主なキー |
|---|---|---|
| `title` | 暗い地に見出し（ロゴの画像か文字） | kicker, logo（画像）か text, sub, bg |
| `brand` | ブランド色の地にロゴの画像が跳ねて定まり、キャッチ | kicker, logo, logo_w, catch（[語, 上の色, 下の色] の並び） |
| `stat` | 大きな数字が数え上がる＋一言＋添える画像（X の投稿など） | kicker, value, unit, sub, card, bg |
| `map` | 地図に点と写真のカード（`map` 命令で build/map.json を先に作る） | kicker, title, places（name, en, label, sub, img, at, card[x,y]） |
| `list` | 企画の名前が下から積み上がる＋右にサムネが重なる | kicker, items, thumbs, more |
| `wall` | バナー・サムネが 3 段で横に流れる | kicker, title, images（文字列か {src, en}）, bg |
| `quotes` | 「こんな声が届いています」→ 声を 1 つずつ文字で（映像の音を止めて音楽を上げる区間） | kicker, intro, items（[本文（\n で改行）, 名前, @ID]）, bgs |
| `xwall` | X の投稿の画像を斜めの壁にだんだん速く貼り、中央に見出し | kicker, title, images, title_at |
| `chapter` | 章の区切り | kicker, title, size, bg |
| `brand_end` | 終わり：アイコン・ロゴ・キャッチ・リンク | icon, logo, catch, links（[[YouTube, チャンネル名], [X, @アカウント]]） |
| `card` | 行ごとに大きさを変えた文字（予告の煽り・題名・お願い）。中央・下・左右にそろえる | lines（[文字, 's'〜'xxl', {en, script, w, color}]）, kicker, pos, dim, foot |
| `photo` | 写真 1 枚（白い縁）＋西暦（数える・巻き戻す）＋年齢＋一言 | img, year, from, age, text, label, side |
| `credits` | エンドロール（名前が流れ、最後に言葉が止まる） | sections, col, win_y, win_h, last |
| `countdown` | 10→1 のカウントダウン | from, lead, dim, dim_box, center |

どの場面も `"overlay": true` で地が透明になり、`over` で映像の上に重ねられる。`hole: [x, y, 幅, 高さ]` はその四角だけ地を抜く（映像の窓・額）。
見た目は scenes.json の `theme`（bg・fg・fg2・accent・line・land・shade・mat・`font: "serif"`（明朝とセリフの英字）・`light: true`（明るい地））で替える。使い方の例は `wedding.md`

書き出す前に `still scenes <名前> 1,3,5` で数コマ見る。文字がはみ出す・カードが重なる・画面の外に出る所を直してから `scenes`。
地図のカードの位置（card）は画面の座標（1920×1080）。点と重ならず、黒帯の内側（y 140〜940）に収める。

## ロゴの画像

透明の PNG が一番よい。白い背景の画像しか無いときは、外側の白を抜いて使う（Pillow の塗りつぶしで角から抜き、ロゴの中の白い箱は残す）。
黒地と黄色の地に載せて、縁が汚れていないか確かめる。

## 名前の札

差し色の小さな四角＋英字の肩書（差し色・字間広め）＋名前（白・太）＋白い細線。場所の札（「東京オフ会」「TOKYO — 90 CREATORS」）も同じ型。
位置は `style.json` の `name_pos`（左上）。顔に重なる絵では位置か絵を替える。肩書が分からないときは空（''）でよい（四角と名前だけになる）。
