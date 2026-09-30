# miniAI-agent

野球に関わる人が誰でもルールを質問できる、野球ルールのミニAIエージェントです。
Jevで一次分類 → confidenceによる分岐 → GPTで再分類 → Pythonで回答ツールへ振り分けます。FastAPIでHTTP APIを提供します。

v0.2の対象は **全日本軟式野球連盟（全軟連）学童部（小学生）の規定** だけです。回答は出典のある事実に限り、大会ごとに決まるルールは推測せず大会規定の確認を案内します。有人レビューへの通知・保存はまだ行いません。`human_review`は人間確認が必要というレスポンスです。

## まず動かす（アカウント・APIキー不要）

Python 3.11以上を用意してください。Windows PowerShell:

```powershell
git clone https://github.com/daieeeego/miniAI-agent.git
cd miniAI-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

Activateは不要です。

macOS / Linuxは取得後、以下で起動できます:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1
```

[Swagger UI](http://127.0.0.1:8000/docs)を開き、`POST /agent` → Try it outで以下を送ります。

```json
{"message": "4年生のピッチャーが今日45球投げました。あと何球投げられる？"}
```

`decision.route: pitch_count`、`decision.source: mock_jev`、`action.tool: pitch_count`が返り、`action.message`に「今日あと15球（45/60球）」と数え方、`action.sources`に出典が入ります。`GET /health`は起動確認用で、外部APIの認証成功を確認するものではありません。

## 分岐ルール

| confidence | 動作 |
| --- | --- |
| 0.85以上 | 分類先の回答ツールへ |
| 0.55以上、0.85未満 | GPTで再分類。GPT未設定・失敗時は人間確認へ |
| 0.55未満 | 人間確認へ |
| Jev呼び出し失敗・不正な応答 | 人間確認へ |

閾値は教材用の仮設定です。confidenceは正答率を保証しません。運用時は評価データで調整してください。Mockのconfidenceはキーワードから計算したデモ値で、Jevの性能評価には使えません。

| APIキーなしで試す入力 | 結果 |
| --- | --- |
| 4年生のピッチャーが今日45球投げました。あと何球投げられる？ | pitch_count：残り15球と数え方 |
| タイブレークと延長のルールは？ | game_rules：大会規定の確認を案内 |
| 一度交代した選手は再出場できる？ | substitution：大会規定の確認を案内 |
| インフィールドフライの条件は？ | GPT未設定ならhuman_review |
| ボークは球数に入る？ | confidence低のためhuman_review |

## 分類と回答の範囲

| route | 内容 | 回答 |
| --- | --- | --- |
| pitch_count | 投球数制限 | 学年・今日・今週の球数を文章から読み取り、残りの球数を計算（`answered`） |
| game_rules | イニング数・コールド・タイブレーク・継続試合 | 大会規定で決まるため確認を案内（`check_tournament_rules`） |
| substitution | 代打・代走・再出場・DH・登録人数 | 再出場は大会規定の確認を案内。DH未導入・登録25名は回答（`check_tournament_rules`） |
| scoring | スコアブックの付け方 | 根拠資料がないため未対応（`not_covered`） |
| play_rules | プレーの判定 | 公認野球規則は扱わないため未対応（`not_covered`） |
| general | 上記以外 | 未対応（`not_covered`） |

出典は全軟連の公開資料（学童部の投球数制限の特別規則・通知、令和4年度の規程変更通知、規程細則）です。
競技者必携の本文は一般公開されていないため、イニング数・コールド・タイブレーク・再出場の条文は持っていません。

## 本物のJev・GPTを使う

JevにはTypeSafeのAPIキーとモデルの利用権限が必要です。GPTフォールバックには別途OpenAI APIの利用設定が必要です。

- [TypeSafe Console](https://console.typesafe.ai/)
- [TypeSafe公式Python SDK](https://github.com/typesafe-ai/typesafe-sdk-python)
- [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs)

APIキーは **Google Cloud Secret Managerに保存し、ADCで取得**します。`.env`、コード、ローカルのキーファイル、ログには保存しません。環境変数に設定するのはSecretのリソース名とモデル名です。

1. Google CloudでSecret Manager APIを有効にします。
2. コンソールでTypeSafe・OpenAIのキーをそれぞれSecretとして登録します。
3. 使用するGoogleアカウントに該当Secretの`Secret Manager Secret Accessor`を付与します。
4. gcloud CLIで`gcloud auth application-default login`を実行します。サービスアカウントの鍵JSONは不要です。ADCはGoogle認証情報を管理する仕組みで、APIキーを保存するものではありません。
5. 次の非秘密設定を行いサーバーを再起動します。

```powershell
$env:JEV_MODE="live"
$env:TYPESAFE_SECRET_VERSION="projects/PROJECT_ID/secrets/typesafe-api-key/versions/1"
$env:OPENAI_SECRET_VERSION="projects/PROJECT_ID/secrets/openai-api-key/versions/1"
$env:OPENAI_MODEL="利用権限のあるStructured Outputs対応モデル名"
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

プロジェクト・Secret名・バージョン・モデル名は実際の値に置き換えます。Jevだけ使う場合、OpenAIの2設定は省略できます。Mockと本物のGPTを組み合わせることもできます。

外部APIを有効にすると本文がTypeSafe／OpenAIへ送信され、利用料が発生する場合があります。まずテスト文で確認してください。APIキーの値や本文はアプリのログとレスポンスに出しません。OpenAIは`store=False`で呼び出します。

Secretは呼び出しごとに取得します。Secret取得は10秒、モデルAPIは20秒のタイムアウトを設定しています。SDK内部の再試行等があるため、リクエスト全体の時間上限ではありません。

## 設定

| 環境変数 | 初期値・用途 |
| --- | --- |
| JEV_MODE | `mock`（`live`へ切替可能） |
| JEV_MODEL | `jev-latest` |
| JEV_HIGH_CONFIDENCE | `0.85` |
| JEV_LOW_CONFIDENCE | `0.55` |
| TYPESAFE_SECRET_VERSION | TypeSafeキーのSecretバージョン名 |
| OPENAI_SECRET_VERSION | OpenAIキーのSecretバージョン名 |
| OPENAI_MODEL | GPTモデル。Secret名と両方設定すると有効 |
| API_TIMEOUT_SECONDS | `20` |

`TYPESAFE_API_KEY`・`OPENAI_API_KEY`はこのアプリでは利用しません。API認証・レート制限は未実装のため、起動コマンドはローカルPCに限定しています。

## テスト

PRでは`CI`ワークフローでテストを実行し、`Merge readiness`で結果を確認します。
GitHub側でテスト成功後だけマージを許可する設定は[CI設定手順](docs/ci.md)を参照してください。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

テストは外部APIを呼びません。Mock、閾値の境界、失敗時の人間確認、無効な入力、SDKアダプター、投球数の計算を確認します。本物の分類精度と認証は、アカウント設定後の確認が必要です。

## 構成

- `app/main.py`: `/health`・`/agent`・Swagger UI
- `app/agent.py`: confidence判定と振り分け
- `app/categories.py`: 分類先の定義（Mockのキーワード、Jevの基準、GPTのプロンプトで共通）
- `app/clients/jev.py`: Mock / Live Jev
- `app/clients/gpt.py`: GPT構造化出力による再分類
- `app/clients/secrets.py`: Secret Manager / ADC
- `app/tools.py`: 回答ツール（投球数の計算、出典付きの定型回答）
- `app/models.py`・`app/config.py`: 入出力と設定の検証
- `tests/test_agent.py`: 外部APIなしのテスト

次の段階では、出典資料からの回答生成、`human_review`の通知、分類精度と回答の正しさの計測を追加します。
