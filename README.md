# channel-pv-maker — チャンネル紹介 PV メーカー（Claude Code / Codex プラグイン）

YouTube チャンネルや参考動画のリンクを渡すと、出演者の**実際の声と映像**をつないだ紹介 PV（予告編・コミュニティ紹介・チャンネルトレーラー）を作ります。

- まず素材を下調べ（動画の一覧・文字起こし・サムネ・アイコン）してから、**構成と見た目の案を選ぶだけの軽い質問**をします
- 構成表で承認をもらってから組み立てます（発言は文脈の通る所で切り、元動画の切り残しや焼き込みの字幕を避けます）
- 題字・数字・地図・企画の一覧・バナーの壁・声の文字・X の投稿の壁・終わりの画面をブラウザで描き、縦書きの明朝の強調テロップを重ねます
- **After Effects があれば AE で組み立て**（あとから AE で直せる .aep が残る）、**無ければ ffmpeg だけで書き出し**ます
- 書き出した後は、音量・一瞬の閃光・全切り替えの一覧・声の文字起こしで検品します

## インストール

**Claude Code**

```bash
claude plugin marketplace add fuuuuuuma/channel-pv-maker
claude plugin install channel-pv-maker@channel-pv-maker
```

**Codex**

```bash
codex plugin marketplace add fuuuuuuma/channel-pv-maker
codex plugin add channel-pv-maker@channel-pv-maker
```

どちらも同じリポジトリです（`.claude-plugin/marketplace.json` を両方が読みます）。

## 使い方

Claude Code か Codex に、リンクを添えて頼むだけです。スキル `channel-pv` が選ばれます。

> このチャンネルの紹介 PV を 3 分くらいで作って https://www.youtube.com/@xxxx

> このコミュニティの入会を考えている人向けに、メンバーの声が伝わる予告編を。参考はこの動画 https://youtu.be/xxxx

最初に下調べ（数分〜十数分）→ 質問 → 構成表の承認 → 組み立て → 検品 の順に進みます。

> 出演者の映像は無いけど、セミナーの告知をアニメ映画の予告っぽく作って。参考はこの予告編 https://youtu.be/xxxx

動きの指示はざっくりで大丈夫です（「ゆっくり寄って」「ポンと出して」「エモく」）。スキルが動きの名前（Motion Prompt の 144 件）に置き換えて、名前で確認してから作ります。

## 必要なもの

| もの | 用途 | 入れ方の例（Mac） |
|---|---|---|
| Python 3.9+ と `requirements.txt` | 全体 | `python3 -m pip install -r requirements.txt` |
| ffmpeg・yt-dlp | 動画の取得と書き出し | `brew install ffmpeg yt-dlp` |
| Node.js 20+ と Chrome | 場面と強調テロップの描画 | `brew install node`（Chrome は普通の Google Chrome でよい） |
| 文字起こし | 発言選び・字幕の時刻 | Apple Silicon は mlx-whisper、それ以外は faster-whisper |
| demucs（任意・おすすめ） | 元動画の BGM を声から外す | `python3 -m pip install demucs` |
| After Effects（任意） | AE での組み立て（2024 以降） | 無ければ ffmpeg で書き出す |

`python3 scripts/pv.py doctor` で足りないものが分かります。Mac（Apple Silicon）で実際に通しています。Windows と Linux は ffmpeg 側の書き出しを想定していますが未検証です。

## 手で使う（コマンド）

```bash
PV=<このリポジトリ>/scripts/pv.py
python3 $PV init ~/pv/mychannel --name mychannel      # 案件フォルダ
cd ~/pv/mychannel
python3 $PV harvest https://www.youtube.com/@xxxx --limit 15
python3 $PV sheets                                    # 絵を選ぶ一覧画像
# build/edl.py（設計図）・build/scenes.json・build/audio.json を書く
python3 $PV prep && python3 $PV edges && python3 $PV faces --apply && python3 $PV crops
python3 $PV plan && python3 $PV scenes && python3 $PV telops && python3 $PV mix
python3 $PV ae build && python3 $PV ae render           # AE が無ければ: python3 $PV compose
python3 $PV qa && python3 $PV preview
python3 $PV motion ゆっくり寄る                        # 動きの名前を探す（番号を渡すと AI への頼み方の全文）
```

## 注意

- **他人の映像・投稿・バナーは、持ち主の許可があるものだけ**使ってください。このツールは YouTube や X に投稿しません（書き出しまで）。
- 有料の生成（AI 動画・音楽・効果音）は、スキルが毎回見積もってから承認を求めます。
- 地図の輪郭は使うときに取得します（日本：dataofjapan/land・出典 国土交通省 国土数値情報）。同梱の書体は Inter と Dela Gothic One（SIL OFL 1.1、`scripts/render/fonts/`）。

## ライセンス

MIT（同梱の書体は各 OFL）。動きの名前の一覧と頼み方（`skills/channel-pv/references/motion-prompt/`）は
[Motion Prompt](https://showheyohtaki.github.io/motion-prompt/)（作者 大滝昇平・MIT License）の写しです。詳しくは `THIRD-PARTY-NOTICES.md`。
