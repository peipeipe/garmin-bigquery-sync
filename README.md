# garmin-bigquery-sync

GitHub Actionsを使用して、Garmin Connectのデータを自動的にGoogle BigQueryに同期します。

このプロジェクトは[GarminDB](https://github.com/tcgoetz/GarminDB)を使用してGarmin ConnectのデータをSQLiteデータベースにダウンロードし、その後BigQueryに同期して分析と可視化を行います。

## 特徴

- 🔄 GarminデータをBigQueryに毎日自動同期
- 📊 日次サマリーとアクティビティを同期
- 🔐 GitHub Secretsによる安全な認証情報管理
- 💾 効率化のため実行間でGarminデータをキャッシュ
- ⚡ workflow_dispatchによる手動トリガーのサポート

## セットアップ

### 1. Google Cloud Platformのセットアップ

#### GCPプロジェクトの作成

1. [Google Cloud Console](https://console.cloud.google.com/)にアクセス
2. 新しいプロジェクトを作成するか、既存のプロジェクトを選択
3. プロジェクトID（例：`my-garmin-project`）をメモ

#### BigQuery APIの有効化

1. GCPプロジェクトで、**APIとサービス > ライブラリ**に移動
2. 「BigQuery API」を検索
3. **有効にする**をクリック

#### BigQueryデータセットの作成

1. [BigQuery Console](https://console.cloud.google.com/bigquery)にアクセス
2. プロジェクト名をクリック
3. **データセットを作成**をクリック
4. データセットID：`garmin_data`（または任意の名前）
5. ロケーション：お好みのリージョンを選択
6. **データセットを作成**をクリック

#### サービスアカウントの作成

1. **IAMと管理 > サービスアカウント**に移動
2. **サービスアカウントを作成**をクリック
3. 名前：`garmin-sync`（または任意の名前）
4. **作成して続行**をクリック
5. 以下のロールを付与：
   - **BigQueryデータ編集者**
   - **BigQueryジョブユーザー**
6. **続行**、**完了**をクリック

#### サービスアカウントキーの生成

1. 作成したサービスアカウントをクリック
2. **キー**タブに移動
3. **鍵を追加 > 新しい鍵を作成**をクリック
4. **JSON**形式を選択
5. **作成**をクリック - JSONファイルがダウンロードされます
6. **このファイルを安全に保管** - GitHub Secretsで使用します

### 2. GitHubリポジトリのセットアップ

#### このリポジトリをフォークまたはクローン

このリポジトリをGitHubアカウントにフォークするか、これらのファイルで新しいリポジトリを作成します。

#### GitHub Secretsの設定

リポジトリの**設定 > シークレットと変数 > Actions**に移動して、以下のシークレットを追加します：

| シークレット名 | 説明 | 例 |
|-------------|-------------|---------|
| `GARMIN_USER` | Garmin Connectのメールアドレス/ユーザー名 | `user@example.com` |
| `GARMIN_PASSWORD` | Garmin Connectのパスワード | `your-password` |
| `GCP_PROJECT_ID` | Google CloudプロジェクトID | `my-garmin-project` |
| `GCP_SA_KEY` | サービスアカウントJSONキーファイルの内容 | JSON全体を貼り付け |

**シークレットの追加方法：**
1. **新しいリポジトリシークレット**をクリック
2. **名前**と**シークレット**の値を入力
3. **シークレットを追加**をクリック

### 3. 同期の実行

#### 自動スケジュール

ワークフローは毎日UTC午前2時に自動的に実行されます。`.github/workflows/sync.yml`でスケジュールを変更できます：

```yaml
schedule:
  - cron: '0 2 * * *'  # 毎日UTC午前2時
```

#### 手動トリガー

1. リポジトリの**Actions**タブに移動
2. **Sync Garmin Data to BigQuery**ワークフローを選択
3. **ワークフローを実行**をクリック
4. ブランチを選択して**ワークフローを実行**をクリック

### 4. BigQueryでデータを表示

1. [BigQuery Console](https://console.cloud.google.com/bigquery)にアクセス
2. プロジェクトを展開
3. `garmin_data`データセットを展開
4. 以下のようなテーブルが表示されます：
   - `daily_summary`
   - `activities`

#### クエリの例

```sql
SELECT 
  day,
  hr_avg,
  hr_max,
  steps,
  distance
FROM `your-project-id.garmin_data.daily_summary`
WHERE day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY day DESC
```

## 設定

### 環境変数

`sync_bq.py`スクリプトは以下の環境変数を受け入れます：

- `GCP_PROJECT_ID`（必須）：Google CloudプロジェクトID
- `DATASET_ID`（オプション）：BigQueryデータセット名（デフォルト：`garmin_data`）

### テーブルの追加

GarminDBから追加のテーブルを同期するには、`sync_bq.py`を編集して`tables_to_sync`リストにテーブル名を追加します：

```python
tables_to_sync = [
    'daily_summary',
    'activities',
    'sleep',           # 必要に応じて
    'monitoring_hr',   # テーブルを追加
]
```

利用可能なすべてのテーブルを確認するには、GarminDBのSQLiteデータベースを調べることができます：

```bash
sqlite3 ~/.GarminDb/garmin.db ".tables"
```

## 技術詳細

### GarminDBラッパー

このプロジェクトには、統計引数なしで`garmindb_cli.py`を呼び出した際に発生する可能性のあるTypeErrorを防ぐラッパースクリプト（`garmindb_wrapper.py`）が含まれています。このラッパーは、統計を必要とする操作（download、import、copy）に常に適切なフラグが設定されていることを保証します。

ラッパーは以下の場合に自動的に`--all`フラグを追加します：
- `--download`、`--import`、`--copy`のような操作が指定されている
- 統計フラグ（`--activities`、`--monitoring`、`--sleep`など）が提供されていない

これにより、内部の`stats`パラメータが`None`になることを防ぎ、コードが`if Statistics.activities in stats:`をチェックしようとした際にTypeErrorが発生するのを防ぎます。

## トラブルシューティング

### 「GarminDB database not found」でワークフローが失敗する

Garminデータがまだダウンロードされていない場合、最初の実行が失敗する可能性があります。ワークフローはインポートステップが失敗しても続行するように設定されています。最初のインポートが成功した後は、その後の実行が正常に動作するはずです。

### statsパラメータのTypeError

`TypeError: argument of type 'NoneType' is not iterable`に関連するエラーが表示される場合は、ラッパースクリプトを使用していることを確認してください：
```bash
# 以下の代わりに：
garmindb_cli.py --download --import --analyze --latest

# 以下を使用：
python garmindb_wrapper.py --download --import --analyze --latest
```

GitHub Actionsワークフローは既にラッパースクリプトを自動的に使用しています。

### 認証の問題

- **Garmin**：`GARMIN_USER`と`GARMIN_PASSWORD`のシークレットが正しいことを確認
- **Google Cloud**：サービスアカウントに必要なBigQuery権限があることを確認
- **GCP_SA_KEY**：中括弧を含むJSONファイルの全内容を貼り付けたことを確認

### BigQueryにデータがない

- **Actions**タブでワークフローログを確認
- Garminインポートステップが正常に完了したことを確認
- GarminDBデータベースに同期されるテーブルのデータがあることを確認

## ローカル開発

### 前提条件

- Python 3.8以上
- Google Cloud SDK（オプション、ローカルテスト用）

### インストール

```bash
# リポジトリをクローン
git clone https://github.com/yourusername/garmin-bigquery-sync.git
cd garmin-bigquery-sync

# 依存関係をインストール
pip install -r requirements.txt
```

### ローカルでの実行

1. Garminデータをダウンロード：
   ```bash
   # 認証情報を設定
   garmindb_cli.py --config
   
   # TypeErrorを防ぐためにラッパーを使用してデータをインポート
   python garmindb_wrapper.py --download --import --analyze --latest
   
   # または特定の統計を指定
   garmindb_cli.py --download --import --analyze --latest --all
   ```

2. Google Cloud認証情報を設定：
   ```bash
   export GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account-key.json
   export GCP_PROJECT_ID=your-project-id
   export DATASET_ID=garmin_data
   ```

3. 同期を実行：
   ```bash
   python sync_bq.py
   ```

## アーキテクチャ

```
┌─────────────────┐
│  Garmin Connect │
└────────┬────────┘
         │ garmindb_cli.py
         ▼
┌─────────────────┐
│ SQLite Database │ ~/.GarminDb/garmin.db
└────────┬────────┘
         │ sync_bq.py
         ▼
┌─────────────────┐
│   BigQuery      │ your-project.garmin_data.*
└─────────────────┘
```

## ライセンス

MIT

## コントリビューション

コントリビューションを歓迎します！プルリクエストをお気軽にお送りください。

## 謝辞

- [GarminDB](https://github.com/tcgoetz/GarminDB) - 優れたGarminデータダウンロードおよび処理ツールの提供