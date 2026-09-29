# テスト・Codexレビュー・マージ判定

PRの更新ごとに、次の順でActionsが動きます。

1. Python 3.11 / 3.12でruff・pytest・マージ判定のNode.jsテストを実行。
2. テスト成功後、公式`openai/codex-action@v1`がPR差分を読み取り専用でレビュー。
3. `Merge readiness`がテスト結果とCodexのJSONレビューを検証。

**PRではテストとCodexの両方が成功し、P0/P1の指摘がない場合だけ判定が成功します。**
P2/P3は参考指摘です。認証未設定、失敗、キャンセル、スキップ、JSON不正を成功扱いしません。
結果はActionsの`Merge readiness`ジョブのSummaryに表示します。自動マージは行いません。

pushではテストだけを確認します。Merge queueでもテストを再実行しますが、CodexレビューはPR時点のものを利用します。
forkからのPRではSecretアクセスを行わず、Codexをスキップしてマージ判定を失敗にします。
外部PRを受け入れる場合は、信頼できる変更をリポジトリ内のブランチに取り込んでレビューしてください。

## Codexの認証設定（初回のみ）

ChatGPTのGitHub接続だけでは公式Codex ActionのAPI認証にはなりません。
OpenAI APIの利用設定が別途必要で、レビューごとにAPI利用料が発生します。

APIキーの保管場所はGoogle Cloud Secret Managerです。GitHubにキーの値や鍵JSONを登録せず、
GitHub OIDC → Workload Identity Federation → Googleサービスアカウントで取得します。
Codex Actionへ渡すため、取得したキーはマスクされた一時的なstep outputを経由します。
これはGitHubランナーの一時ファイルを利用する仕組みで、リポジトリ、成果物、ログ、開発PCには保存しません。
ランナーはGitHubが提供する使い捨てのUbuntuです。

1. Secret ManagerにCodexレビュー用のOpenAI APIキーを登録。
2. GitHubを信頼するWorkload Identity Pool / OIDC Providerを構成。
   issuerは`https://token.actions.githubusercontent.com`。
   `google.subject=assertion.sub`、`attribute.repository=assertion.repository`をマッピングし、
   このリポジトリのPRイベントだけを許可する属性条件を付けます。例えば:

   ```text
   assertion.repository == 'daieeeego/miniAI-agent' && assertion.event_name == 'pull_request'
   ```

3. レビュー専用サービスアカウントを作り、上のリポジトリのprincipalSetに
   `roles/iam.workloadIdentityUser`を付与します。サービスアカウントには、レビュー用Secretだけの
   `roles/secretmanager.secretAccessor`を付与します。Secret Manager API・IAM Credentials APIも有効にします。
4. GitHubの`Settings → Secrets and variables → Actions → Variables`に以下を登録します。
   ValuesとSecretsどちらに登録しても読み込めます。プロジェクト識別子やリソース名は通常Variablesに置けます。
   必要ならSecretsに保存し、Variablesと同名の場合はVariablesを優先します。

| Variable | 設定例 |
| --- | --- |
| GCP_WIF_PROVIDER | `projects/123456789/locations/global/workloadIdentityPools/github/providers/github` |
| GCP_SERVICE_ACCOUNT | `codex-review@PROJECT_ID.iam.gserviceaccount.com` |
| CODEX_OPENAI_SECRET_VERSION | `projects/PROJECT_ID/secrets/codex-openai-key/versions/1` |
| CODEX_MODEL | 任意。空ならCodex Actionの既定モデル |

値は自分の環境に置き換えます。APIキーの値をこのチャットに送る必要はありません。
設定後、PRの失敗したActionsを再実行してください。

## テスト失敗時にマージを禁止する設定

**Actionsを追加しただけでは、GitHubのマージボタンを禁止できません。**
`main`のブランチ保護ルールを別途設定します。

1. `Settings → Branches → Add branch protection rule`を開く。
2. Branch name patternを`main`にする。
3. `Require a pull request before merging`を有効にする。
4. `Require status checks to pass before merging`を有効にする。
5. 必須チェックに **`Merge readiness`** を指定する。
6. `Require branches to be up to date before merging`を有効にする。
7. 管理者も同じ制約にする場合は`Do not allow bypassing the above settings`を有効にする。
8. Force push・ブランチ削除は許可せずに保存する。

チェック候補が出ない場合は、このPRのActionsが一度走ってから再度設定画面を開きます。
保護ルールは現在のChatGPT GitHub連携にAdministration権限がないため、こちらから設定できていません。
Codexの認証と保護ルールの設定が済むまでは、マージ制御が完成したとは扱わないでください。

## 検証コマンド

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
node --test .github/scripts/merge-readiness.test.cjs
```

Node.js 20以上が必要です。テストは外部APIやAPIキーを使いません。
Codexによる問題なしの判定は、バグがないことの保証ではありません。

## 公式ドキュメント

- [Codex GitHub Action](https://developers.openai.com/codex/github-action/)
- [Google GitHub Actions auth](https://github.com/google-github-actions/auth)
- [GitHubブランチ保護](https://docs.github.com/en/repositories/configuring-branches-and-merges-in-your-repository/managing-protected-branches/about-protected-branches)
