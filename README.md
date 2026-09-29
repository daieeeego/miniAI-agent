# miniAI-agent

Jevで一次分類 → confidenceによる分岐 → GPTで再分類 → Pythonでツールへ振り分ける、学習用ミニAIエージェントです。FastAPIでHTTP APIを提供します。

v0.1は **AWS / Snowflake / Datadog / general の分類とダミーツール実行**までです。クラウド操作、DB接続、有人レビューへの通知・保存は行いません。`human_review`は人間確認が必要というレスポンスです。

## まず動かす（アカウント・APIキー不要）

Python 3.11以上を用意してください。Windows PowerShell:

```powershell
git clone https://github.com/daieeeego/miniAI-agent.git
cd miniAI-agent
git switch feature/v0.1-initial-agent
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1
```

Activateは不要です。PRマージ後は`main`でも利用できます。

macOS / Linuxは取得後、以下で起動できます:

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements-dev.txt
.venv/bin/python -m uvicorn app.main:app --reload --host 127.0.0.1
```

[Swagger UI](http://127.0.0.1:8000/docs)を開き、`POST /agent` → Try it outで以下を送ります。

```json
{"message": "AWS S3 RDS Athena IAMの相談"}
```

`decision.route: aws`、`decision.source: mock_jev`、`action.tool: aws_tool`、`action.simulated: true`が返ります。`GET /health`は起動確認用で、外部APIの認証成功を確認するものではありません。

## 分岐ルール

| confidence | 動作 |
| --- | --- |
| 0.85以上 | 分類先のダミーツールへ |
| 0.55以上、0.85未満 | GPTで再分類。GPT未設定・失敗時は人間確認へ |
| 0.55未満 | 人間確認へ |
| Jev呼び出し失敗・不正な応答 | 人間確認へ |

閾値は教材用の仮設定です。confidenceは正答率を保証しません。運用時は評価データで調整してください。Mockのconfidenceはキーワードから計算したデモ値で、Jevの性能評価には使えません。

| APIキーなしで試す入力 | 結果 |
| --- | --- |
| AWS S3 RDS Athena IAMの相談 | awsのダミーツール |
| Snowflake Warehouse Roleの相談 | snowflakeのダミーツール |
| Datadog Monitor Metric Alertの相談 | datadogのダミーツール |
| AthenaでS3のデータを検索したい | GPT未設定ならhuman_review |
| AWSとSnowflakeとDatadogの相談 | confidence低のためhuman_review |

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

PRでは、テスト → Codexレビュー → `Merge readiness`の順にチェックします。
Codexの認証設定とmainの必須チェック設定は[CI設定手順](docs/ci.md)を参照してください。
未設定のCodexレビューを成功扱いにはしません。

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
```

テストは外部APIを呼びません。Mock、閾値の境界、失敗時の人間確認、無効な入力、SDKアダプターを確認します。本物の分類精度と認証は、アカウント設定後の確認が必要です。

## 構成

- `app/main.py`: `/health`・`/agent`・Swagger UI
- `app/agent.py`: confidence判定と振り分け
- `app/clients/jev.py`: Mock / Live Jev
- `app/clients/gpt.py`: GPT構造化出力による再分類
- `app/clients/secrets.py`: Secret Manager / ADC
- `app/tools.py`: ダミーツール
- `app/models.py`・`app/config.py`: 入出力と設定の検証
- `tests/test_agent.py`: 外部APIなしのテスト

次の段階ではダミーツールを読み取り専用の実APIに置き換え、分類精度とフォールバック率を計測できます。
