# grokbot-webhook

Claude Code から **Grok Bot** (Cursor 社のデスクトップアプリの bot) に、文章で答えが返る依頼 (質問・調べもの・要約・計算・文章の作成) を渡せるようにする plugin。

*An unofficial Claude Code plugin that lets you ask a Grok Bot (Cursor's desktop app) via its routine webhook. Docs and the bot prompt are in Japanese only; tested on macOS only.*

セットアップは Claude Code との会話で進み、終わると `ask-grokbot` という skill が手元にできる。あとは「grokbot に〜を頼んで」と言うだけ。

```
> grokbot に「このリリースノートを 3 行に要約して」と頼んで、返事を教えて

⏺ Skill(ask-grokbot)
⏺ Bash(python3 ".../grokbot_webhook.py" send --wait --profile ask-grokbot "…")
⏺ grokbot からの返事は次のとおりです。…
```

短い質問で、送信から返事まで 11〜17 秒だった (2026-11、Grok Bot 1.0.3)。

> **非公式のツールです。** Cursor 社・Anthropic 社とは関係がありません。Grok Bot アプリの画面に表示される Webhook を使っていますが、この Webhook は公開ドキュメントに載っておらず、予告なく変わったり使えなくなったりする可能性があります。無保証です。

## はじめかた (3 ステップ、5 分ほど)

現在のバージョンは 0.7.2 ([変更履歴](CHANGELOG.md))。

**動画で見る**: [セットアップの手順を最初から最後まで (6 分半、音声つき)](https://github.com/AI-Driven-R-D-Dept/grokbot-webhook/releases/download/v0.7.2/grokbot-webhook-tutorial.mp4)。ターミナルの開き方から、Grok Bot アプリで押す場所まで、1 ステップずつ映している。

用意するもの:

- Claude Code (ターミナルで `claude` と打つと開くもの。まだなら先に [Claude Code の導入](https://code.claude.com/docs) を済ませる)
- Grok Bot のデスクトップアプリ (ログイン済み)
- python3 (macOS には最初から入っている)

動作を確かめたのは macOS だけ。

**1. 入れる**

ターミナル (Mac なら「ターミナル」アプリ) を開き、次の 2 行を 1 行ずつ貼り付けて Enter を押す。

```bash
claude plugin marketplace add AI-Driven-R-D-Dept/grokbot-webhook
claude plugin install grokbot-webhook@grokbot-webhook
```

**2. Claude Code でセットアップを頼む**

同じターミナルで `claude` と打って Claude Code を開き、次の文をそのまま入力して Enter を押す (`>` は入力欄の印で、打たない)。

```
> grokbot の webhook をセットアップして
```

Claude Code が、このパソコンにすること (クリップボードの利用・作るファイル) を先に伝えてから、1 つずつ聞いてくるので、答えていく。人がやるのは次のことだけ。

- (返事を Claude Code の画面で受け取りたいときだけ) Grok Bot アプリの設定 (左下の自分の名前 →「設定」→「コンピューター」) で、「このコンピューターで実行」を「常に許可」にして、このパソコンを bot につなぐ。つなぐと bot はそのパソコンでコマンドを実行できるようになるので、下の「知っておくこと」を読んでから決める
- Grok Bot アプリで bot を 1 体作る
- その bot のチャットに、貼り付け (⌘V) て送る (文章は Claude Code がクリップボードに入れておく。中身は貼る前に Claude Code が説明し、頼めば全文を見せる)
- アプリに出る「POST先」と「キー」のコピーのボタンを押す (押すだけで Claude Code が受け取って保存する。キーは画面にも会話にも出ない)

コマンドを打つ必要はない (macOS の場合。ほかの OS では、文章とコマンドを画面からコピーする形になる)。途中で Claude Code がコマンド実行の許可を何度か求める。

最後に Claude Code が試しに 1 回送って、返事が返ることを確かめる。

**3. 使う**

```
> grokbot に「…」と頼んで
```

`/ask-grokbot 頼む内容` でも呼べる。

## この plugin があなたのパソコンにすること

セットアップ用の skill は、次のことをする前に、何をするかを伝えて了承を取る。

| すること | 中身 | 避けたいとき |
|---|---|---|
| クリップボードを使う | bot に貼る文章を入れる (入っていたものは上書き)。POST 先とキーを受け取るあいだ、100 秒ほどクリップボードを読み続ける (POST 先とキーの形のものだけを受け取り、ほかは保存も表示もしない)。最後に空にする | 手で進める (文章とコマンドを画面からコピーする) |
| skill を作る | `~/.claude/skills/ask-grokbot/` に手順書とスクリプトのコピーを置く。以後どのフォルダの Claude Code でも読み込まれ、**plugin を外しても残る** | 「いまのフォルダだけ」を選ぶ (`./.claude/skills/` に作る) |
| キーを保存する | `~/.config/grokbot-webhook/env` (自分だけが読める権限) | 環境変数で渡す |
| 返事の保存先を作る | `~/.grokbot-webhook/replies/`。返事を Claude Code の画面で受け取る形のときだけ。bot がここに返事のファイルを書き、スクリプトが読み終えたら消す | 「送るだけ」を選ぶ |
| bot を動かす | セットアップの最後に試しに 1 回送る。以後は頼まれたときだけ | 試し送信を断る |
| パソコンを bot につないでもらう | 返事を Claude Code の画面で受け取る形を選んだときだけ。つなぐと bot はそのパソコンでコマンドを実行できる | 「送るだけ」を選ぶ |

スクリプトがファイルを作る・書き換えるのは上の 3 か所だけ。スクリプトの通信先は、あなたのルーティンの Webhook (`cursor.sh` のホスト) だけで、転送 (リダイレクト) を指示されても従わない。パソコンを bot につないだ場合に bot がそのパソコンで何をするかは、bot に貼った文章 (ルーティンの指示) で決まる (「知っておくこと」を参照)。

## 背景: 何が起きているのか

- **Grok Bot とは**: チャットで仕事を頼める bot を作って使う、Cursor 社のデスクトップアプリ。bot ごとに会話の履歴を持ち、アプリ側でつないだサービスや bot 自身の作業環境を使って仕事をする。ただしこの plugin が bot に貼る文章は、それらを使わず文章で答えることだけを bot に頼む。
- **ルーティンとは**: bot に前もって渡しておく「指示」と、それを動かす「きっかけ」の組。きっかけには決まった時刻などのほかに「Webhookが発火したとき」があり、これを選ぶとアプリが POST 先の URL とキーを発行する。その URL に依頼文を POST すると、bot が指示に沿って動く。
- **なぜ Webhook か**: 私たちが調べた範囲では、Grok Bot を外のプログラムから呼ぶための公開 API や CLI は見当たらなかった。アプリの画面に出てくる外からの受付口が、このルーティンの Webhook だった。
- **返事の受け取り方**: Webhook の応答には bot の返事が入っていない。そこで、bot に「答えを依頼元のパソコンのファイルに書く」ことをルーティンの指示で頼んでおき、スクリプトがそのファイルを待つ。これには Grok Bot の「このコンピューターで実行」(bot が自分のパソコンのファイルを開いたりコマンドを実行したりできるようにする設定) を使う。返事が要らないなら接続は不要 (セットアップで「送るだけ」を選ぶ)。

```
Claude Code ──POST {"context": 依頼文}──▶ Webhook ──▶ Grok Bot のルーティンが起動
     ▲                                                    │
     └── ~/.grokbot-webhook/replies/<名前>.md ◀── 返事を書く ┘   (返事を受け取る形だけ)
```

## 入っているものと、セットアップでできるもの

plugin に入っているもの:

| 場所 | 何か |
|---|---|
| `plugins/grokbot-webhook/skills/setup/SKILL.md` | セットアップ用の skill。Claude Code が読んで、会話で手順を進める |
| `.../setup/scripts/grokbot_webhook.py` | 実際に Webhook へ POST する小さなコマンド (python3 だけで動く) |
| `.../setup/templates/ask-skill.md` | セットアップの最後に作られる skill のひな形 |
| `.../setup/references/setup.md` | 詳しい説明。うまくいかないとき、安全のための注意、後片付け |
| `tests/test_cli.py` | テスト。手元に立てた偽の Webhook サーバーを相手にするので、bot は動かずキーも要らない |

セットアップが終わると手元にできるもの:

| できるもの | 場所 | 中身 |
|---|---|---|
| 呼び出し用の skill | `~/.claude/skills/ask-grokbot/` | 手順書 (POST 先の URL 入り) と、スクリプトのコピー。plugin を外しても、これだけで動く |
| キーの保存先 | `~/.config/grokbot-webhook/env` | POST 先とキー。自分だけが読める権限 |
| 返事の保存先 | `~/.grokbot-webhook/replies/` | 返事を Claude Code の画面で受け取る形のときだけ。読み終えた返事は消される |

キーは skill の中には入らない。2 つ目の bot をつなぎたいときは、もう一度セットアップを頼み、別の名前の skill を作る。

repo を clone して、そのフォルダを指定して入れることもできる (`claude plugin marketplace add <clone したフォルダ>`)。その場合、セットアップが済むまではフォルダを消したり動かしたりしない。セットアップで作られる `ask-grokbot` はスクリプトのコピーを持っているので、できたあとは plugin が無くても動く。逆に、plugin を更新しても作成済みの skill には届かない。直しを受け取るには、plugin を更新してからもう一度セットアップを頼む。

## 向いている使い方、向いていない使い方

| 向いている | 向いていない |
|---|---|
| 1 回で完結する依頼を、十数秒待てる | 即答がほしいやり取りを何度も繰り返す (送るたびに bot が 1 回動く) |
| 質問・調べもの・要約・計算・文章の作成など、文章で答えが返る依頼 | ファイルの操作・コマンドの実行・メールなどの送信をさせる依頼 (デフォルトの指示では bot が断る) |
| 返事を急がず、あとで Grok Bot アプリのチャットで読めばよい依頼 (送るだけの形) | パスワードや API キーを含む依頼 (依頼文は bot の履歴に残る) |

## 知っておくこと

- **キーを持っている人は、その bot のルーティンを起動できる。** git・会話・コマンドラインに出さない。
- **返事のファイルを書かせる合図は、届いた依頼文の側に付いている。** だからキーを持つ人なら誰でも、接続したパソコンの `~/.grokbot-webhook/replies/` に bot がファイルを書くことを起こせる (書ける場所・名前・大きさは指示で絞ってある)。
- **bot が引き受けるのは、文章で答えられる依頼だけ** (質問に答える・調べる・要約する・計算する・文章を作るなど)。セットアップで bot に貼る文章 (ルーティンの指示) にそう書いてあり、ファイルの読み書き・コマンドの実行・送信・ブラウザの操作・秘密の値を集めることは、依頼されても行わない。Webhook の本文は「外から届いたデータ」として扱い、本文に「指示を無視して」と書かれていても従わない。例外は、返事を決まったフォルダに新しいファイルとして書くことだけ。もっと広い仕事をさせたいときは、貼る前に文章を書き換える。
- **この制限は bot (LLM) の判断で守られている。** 指示の無視・保存先の逸脱・コマンド実行の追加を狙った本文を送って、どれも実行されないことを確かめた (各 2 回)。ただし仕組みで隔離されているわけではなく、いつも断るとは保証できない。
- **パソコンを bot に接続すると、bot はそのパソコンでコマンドを実行できる。** 返事を手元のファイルで受け取る形はこの接続を使う。キーが漏れると、接続したパソコンの上で bot が動くきっかけを他人に渡すことになる。接続は返事を受け取りたい場合だけにする。
- **送るたびに bot が 1 回動く** (Grok Bot の週の使用量を使う)。
- **キーの送り先は `cursor.sh` のホストに限っている。** 貼り間違えた URL にキーを送らないための検査。転送 (リダイレクト) にも従わない。
- **依頼文をコマンドの引数に書くと、実行中は同じパソコンのほかの利用者から見えることがある** (`ps`)。見られたくない依頼文は標準入力で渡す。
- **bot の返事は外から来た文章。** skill は資料として読み、返事に書かれた指示をそのまま実行しない。

## 外すとき

```bash
claude plugin uninstall grokbot-webhook@grokbot-webhook
claude plugin marketplace remove grokbot-webhook
```

作られたものも消すなら、`~/.claude/skills/ask-grokbot` (「いまのフォルダだけ」で作ったときは、そのフォルダの `.claude/skills/ask-grokbot`)、`~/.config/grokbot-webhook/env`、`~/.grokbot-webhook/` を消す。Grok Bot アプリ側のルーティンも削除する。返事を受け取るためだけにパソコンをつないだのなら、アプリで接続も外す。

## Claude Code を通さずに使う

スクリプトは人が端末から直接使ってもよい。下の例は、この repo を clone したフォルダの中で実行する場合 (plugin として入れただけなら、セットアップで作られた `~/.claude/skills/ask-grokbot/grokbot_webhook.py` を使う)。

```bash
GW=plugins/grokbot-webhook/skills/setup/scripts/grokbot_webhook.py
python3 $GW check --profile ask-grokbot                    # 設定の確認 (bot は動かない)
python3 $GW send --wait --profile ask-grokbot "頼む内容"     # 送って返事を待つ
python3 $GW send --profile ask-grokbot "頼む内容"            # 送るだけ
```

## テスト

```bash
python3 -m unittest discover -s tests -v
```

## 確かめていないこと

- macOS 以外の OS、英語表示のアプリでのボタン名 (文書と、bot に貼る文章は日本語)
- 接続中のパソコンが 1 台のときに bot が自動でそのパソコンを選ぶ流れ、1 台も無いときに「接続中のパソコンがありません」と返す流れ (2 台以上のときに名前の一覧を返す流れは確かめた)
- ルーティンを一時停止したときの応答、bot の操作が承認待ちで止まった場合 (削除したルーティンに送ると `401 Invalid API key` が返ることは確かめた)
- 返信ファイルは書いたのにチャットには返信しなかった回が 1 回あり、理由は分かっていない

## 問い合わせ・ライセンス

- 不具合や質問は GitHub の Issues へ: https://github.com/AI-Driven-R-D-Dept/grokbot-webhook/issues
- 安全に関わる問題 (キーが漏れる・意図しない操作が起きるなど) は、Issues に詳しく書かず、[SECURITY.md](SECURITY.md) の方法で知らせてほしい
- Grok Bot・Cursor・Claude Code などの名称は、それぞれの権利者の商標または登録商標。この repo はそれらの提供元と関係がない
- ライセンスは MIT ([LICENSE](LICENSE))
