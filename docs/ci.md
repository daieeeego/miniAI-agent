# CIとマージ判定

`CI` GitHub Actionsワークフローを使います。PR・main以外へのpush・Merge queueで動きます。
Python 3.11 / 3.12で、ruff、pytest、マージ判定テストを実行します。

`Merge readiness`ジョブは、必須のテストジョブがすべて成功した時だけ成功します。
テストの失敗・キャンセル・スキップ時は失敗します。自動マージは行いません。

## mainでテスト成功を必須にする

Actionsを追加しただけでは、GitHubのマージボタンを制御しません。`main`にブランチ保護ルールを設定します。

1. リポジトリの`Settings → Branches → Add branch protection rule`を開く。
2. Branch name patternに`main`を指定する。
3. `Require a pull request before merging`と`Require status checks to pass before merging`を有効にする。
4. 必須チェックとして **`Merge readiness`** を選ぶ。
5. 必要に応じて`Require branches to be up to date before merging`を有効にし、保存する。

チェック名が選択肢にない時は、先にPRでCIを一度実行します。
現在のGitHub連携にはブランチ保護の設定権限がないため、ルールはGitHubの設定画面で有効にしてください。

## ローカルで確認

```powershell
.\.venv\Scripts\python.exe -m pytest -q
.\.venv\Scripts\python.exe -m ruff check .
.\.venv\Scripts\python.exe -m ruff format --check .
node --test .github/scripts/merge-readiness.test.cjs
```

Node.jsがあるCIランナーで動きます。マージ判定ロジックのテストは外部APIやキーを使いません。
