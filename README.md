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
   - **BigQuery データ編集者**
   - **BigQuery ジョブユーザー**
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

ワークフローは毎日UTC午後9時（日本時間午前6時）に自動的に実行されます。`.github/workflows/sync.yml`でスケジュールを変更できます：

```yaml
schedule:
  - cron: '0 21 * * *'  # 毎日UTC午後9時（日本時間午前6時）
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
- `DATASET_LOCATION`（オプション）：BigQueryデータセットのロケーション（デフォルト：`US`）
  - 例：`US`, `EU`, `asia-northeast1`（東京）など
  - GitHub Actions workflowで設定する場合は環境変数に追加してください

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

### 空テーブルの作成

バージョン2.0以降、このプロジェクトは**データが存在しない場合でも空のBigQueryテーブルを作成します**。これにより以下のメリットがあります：

- 初回実行時や新しいテーブル追加時にスキーマを確認できる
- BigQueryでテーブル構造を見ながらクエリを作成できる
- データがない期間でもテーブルが表示される

空テーブルは事前定義されたスキーマを使用して作成されます。現在対応しているテーブル：
- `daily_summary` - 日次サマリー（心拍数、歩数、カロリーなど）
- `activities` - アクティビティ記録（ランニング、サイクリングなど）
- `sleep` - 睡眠データ（睡眠時間、睡眠段階など）

### データの追加モード

バージョン2.0以降、BigQueryへのデータ同期は**追加モード（append）**を使用します：

- 初回実行時：新しいテーブルを作成してデータを投入
- 2回目以降：既存のテーブルにデータを追加（上書きではなく追加）
- データの重複管理は現在実装されていないため、同じ日のデータを複数回同期すると重複する可能性があります

将来的には重複排除機能の追加を検討しています。

## 技術詳細

### GarminDBラッパー

このプロジェクトには、統計引数なしで`garmindb_cli.py`を呼び出した際に発生する可能性のあるTypeErrorを防ぐラッパースクリプト（`garmindb_wrapper.py`）が含まれています。このラッパーは、統計を必要とする操作（download、import、copy）に常に適切なフラグが設定されていることを保証します。

ラッパーは以下の場合に自動的に`--all`フラグを追加します：
- `--download`、`--import`、`--copy`のような操作が指定されている
- 統計フラグ（`--activities`、`--monitoring`、`--sleep`など）が提供されていない

これにより、内部の`stats`パラメータが`None`になることを防ぎ、コードが`if Statistics.activities in stats:`をチェックしようとした際にTypeErrorが発生するのを防ぎます。

## トラブルシューティング

### 「GarminDB database not found」でワークフローが失敗する

初回実行時にGarminデータがまだダウンロードされていない場合、このエラーが発生する可能性があります。この場合：

1. **Actions**タブでワークフローログを確認
2. Garminインポートステップが正常に完了したことを確認
3. データのダウンロードには時間がかかる場合があります
4. 2回目以降の実行は通常正常に動作します

バージョン2.0以降、インポートが失敗した場合でも前回キャッシュされたデータベースがあればBigQuery同期を試みます。

### BigQueryにデータがない

以下を確認してください：

1. **ワークフローログを確認**
   - **Actions**タブで最新のワークフロー実行を開く
   - 各ステップのログを確認
   - エラーメッセージを探す

2. **BigQueryテーブルの確認**
   - バージョン2.0以降は、データがなくても空テーブルが作成されます
   - [BigQuery Console](https://console.cloud.google.com/bigquery)で`garmin_data`データセットを確認
   - テーブルが存在するか、行数が0かを確認

3. **同期サマリーを確認**
   - ワークフローログの最後に表示される「Sync Summary」セクションを確認
   - 各テーブルの行数とステータスが表示されます：
     ```
     ✨ Sync Summary
     ============================================================
     Project: your-project-id
     Dataset: garmin_data
     
     Table Row Counts:
       ✅ daily_summary: 30 rows
       ✅ activities: 15 rows
       ⚪ sleep: 0 rows
     
     Total rows synced: 45
     Tables processed: 3/3
     Failed: 0/3
     ============================================================
     ```

4. **GarminDBデータベースの確認**
   - ローカルで実行している場合：
     ```bash
     sqlite3 ~/.GarminDb/garmin.db "SELECT COUNT(*) FROM daily_summary;"
     ```

### 空テーブルの確認

BigQueryで空テーブルが作成されているか確認するには：

```sql
SELECT table_name, row_count 
FROM `your-project-id.garmin_data.__TABLES__`
ORDER BY table_name;
```

### データの重複

バージョン2.0以降は追加モード（append）を使用するため、同じデータを複数回同期すると重複する可能性があります。重複を確認するには：

```sql
SELECT day, COUNT(*) as count
FROM `your-project-id.garmin_data.daily_summary`
GROUP BY day
HAVING count > 1
ORDER BY day DESC;
```

重複を削除するには、一時的にテーブルを削除して再同期してください。

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

### ワークフローが成功してもBigQueryにデータがない場合

これは本プロジェクトのバージョン1.xで発生していた主な問題です。バージョン2.0で以下の改善を実装しました：

1. **インポートステップの失敗検出**
   - `continue-on-error: true`を削除し、真のエラーは即座に失敗するように
   - データベースが存在する場合は、新規データなしでも同期を継続

2. **空テーブルの作成**
   - データがなくてもテーブル構造を確認できるよう空テーブルを作成

3. **詳細なログ出力**
   - 各テーブルの行数
   - BigQueryテーブルの合計行数
   - エラーの詳細（テーブル名、ステージ、例外タイプ）

4. **追加モード**
   - データの上書きではなく追加により、過去データを保持

これらの改善により、問題の診断と解決が容易になります。

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