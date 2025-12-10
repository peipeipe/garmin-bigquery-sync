# garmin-bigquery-sync

Garmin ConnectのデータをGoogle BigQueryに自動同期するETLパイプライン。

[GarminDB](https://github.com/tcgoetz/GarminDB)でGarmin ConnectからSQLiteにデータを取得し、BigQueryに同期する。GitHub Actionsで毎日自動実行。

## 同期されるデータ

| テーブル | 内容 |
|---------|------|
| `daily_summary` | 日次サマリー（心拍数、歩数、カロリー、ストレス、SpO2など） |
| `activities` | アクティビティ（ランニング、サイクリングなど） |
| `sleep` | 睡眠データ |
| `stress` | ストレスデータ |
| `weight` | 体重・体組成 |
| `resting_hr` | 安静時心拍数 |

## セットアップ

### 1. GCPの準備

1. [Google Cloud Console](https://console.cloud.google.com/)でプロジェクトを作成
2. BigQuery APIを有効化
3. サービスアカウントを作成し、以下のロールを付与：
   - BigQuery データ編集者
   - BigQuery ジョブユーザー
4. サービスアカウントのJSONキーをダウンロード

### 2. GitHub Secretsの設定

リポジトリの **Settings > Secrets and variables > Actions** で以下を設定：

| シークレット | 内容 |
|-------------|------|
| `GARMIN_USER` | Garmin Connectのメールアドレス |
| `GARMIN_PASSWORD` | Garmin Connectのパスワード |
| `GCP_PROJECT_ID` | GCPプロジェクトID |
| `GCP_SA_KEY` | サービスアカウントのJSONキー（全文） |

### 3. 実行

- **自動実行**: 毎日 UTC 21:00（JST 06:00）に実行
- **手動実行**: Actions タブから "Run workflow" で実行

## 同期モード

| モード | 説明 |
|--------|------|
| `incremental` | 直近30日分を取得し、MERGE（upsert）で同期。重複なし。 |
| `full_refresh` | 2015年からの全データを取得し、テーブルを置換。 |

手動実行時に選択可能。スケジュール実行は incremental。

## ローカル実行

```bash
# 依存関係インストール
pip install -r requirements.txt

# Garminデータ取得
python garmindb_wrapper.py --download --import --analyze --latest

# BigQuery同期
export GCP_PROJECT_ID=your-project-id
export GOOGLE_APPLICATION_CREDENTIALS=/path/to/key.json
python sync_bq.py
```

## アーキテクチャ

```
Garmin Connect API
       |
       v
garmindb_wrapper.py (GarminDB)
       |
       v
~/HealthData/DBs/*.db (SQLite)
       |
       v
sync_bq.py (MERGE/upsert)
       |
       v
BigQuery: garmin_data.*
```

## ライセンス

MIT
