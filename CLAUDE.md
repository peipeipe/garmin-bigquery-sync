# CLAUDE.md

このファイルは、このリポジトリのコードを扱う際に Claude Code (claude.ai/code) へのガイダンスを提供します。

## プロジェクト概要

**garmin-bigquery-sync** は、GitHub Actions を使用して Garmin Connect のフィットネスデータを Google BigQuery に同期する自動 ETL パイプラインです。データフロー：Garmin Connect API → GarminDB CLI → SQLite → BigQuery。

## コマンド

```bash
# 依存関係のインストール
pip install -r requirements.txt

# テストの実行
python test_sync_bq.py
python test_garmindb_wrapper.py

# Garminデータのダウンロード（~/.GarminDb/GarminConnectConfig.jsonに設定が必要）
python garmindb_wrapper.py --download --import --analyze --latest

# SQLiteからBigQueryへの同期（GCP_PROJECT_ID環境変数が必要）
python sync_bq.py
```

## アーキテクチャ

### データフロー
```
Garmin Connect API
       ↓
garmindb_wrapper.py  →  設定を検証し、statsがNoneの場合のTypeErrorを防止
       ↓
garmindb_cli.py      →  GarminDBライブラリを介してデータをダウンロード
       ↓
~/.GarminDb/garmin.db (SQLite)
       ↓
sync_bq.py           →  SQLiteを読み取り、BigQueryにアップロード
       ↓
BigQuery: garmin_data.{daily_summary, activities, sleep}
```

### 主要モジュール

- **`sync_bq.py`**: メイン同期エンジン。BigQueryのデータセット/テーブルを作成し、SQLiteから読み取り、追加モードでアップロード（履歴データを保持）。データが存在しない場合は、事前定義されたスキーマで空のテーブルを作成。

- **`garmindb_wrapper.py`**: GarminDB CLI のラッパーで、`stats`設定パラメータがNoneの場合のTypeErrorを防止。設定に必要なデフォルト値があることを保証し、必要に応じて`--all`フラグを追加。

- **`.github/workflows/sync.yml`**: UTC午後9時に毎日実行されるGitHub Actionsワークフロー。実行間で`~/.GarminDb`、`~/.garth`、`~/HealthData`をキャッシュ。Garminインポートが失敗した場合、キャッシュされたデータにフォールバック。

### 同期モード

ワークフローは2つのモードをサポート：

- **incremental（デフォルト）**: 最新30日間のデータをダウンロードし、BigQueryに追加（append）
- **full_refresh**: 過去2年間の全データをダウンロードし、BigQueryを置換（replace）

手動実行時にGitHub Actionsの「Run workflow」から選択可能。

### 環境変数

```bash
GCP_PROJECT_ID      # 必須：Google Cloudプロジェクト ID
DATASET_ID          # オプション：BigQueryデータセット名（デフォルト：garmin_data）
DATASET_LOCATION    # オプション：BigQueryのロケーション（デフォルト：US）
SYNC_MODE           # オプション：incremental または full_refresh（デフォルト：incremental）
```

### GitHub Actions シークレット

- `GARMIN_USER` / `GARMIN_PASSWORD`: Garmin Connectの認証情報
- `GCP_PROJECT_ID`: Google Cloudプロジェクト
- `GCP_SA_KEY`: サービスアカウントのJSONキー

## GarminConnectConfig.json フォーマット

**重要**: GarminDBは`data`セクション内にフラットなキーを期待します（ネストしたオブジェクトではありません）。

```json
{
  "credentials": {
    "user": "your@email.com",
    "password": "your_password"
  },
  "data": {
    "download_days": 3,
    "download_latest_activities": 10,
    "download_all_activities": 100,
    "monitoring_start_date": "2024-11-01",
    "monitoring_end_date": "2024-12-01",
    "activities_start_date": "2024-11-01",
    "activities_end_date": "2024-12-01",
    "sleep_start_date": "2024-11-01",
    "sleep_end_date": "2024-12-01",
    "rhr_start_date": "2024-11-01",
    "rhr_end_date": "2024-12-01",
    "weight_start_date": "2024-11-01",
    "weight_end_date": "2024-12-01"
  },
  "settings": {
    "metric": true
  }
}
```

## データベース構造

GarminDBは複数のSQLiteデータベースファイルを使用：

- **garmin.db**: daily_summary, sleep, stress, weight, resting_hr
- **garmin_activities.db**: activities

データは `~/HealthData/DBs/` に保存される。

## BigQueryテーブルスキーマ

`sync_bq.py`で事前定義されたスキーマを持つ6つのテーブル：
- `daily_summary`: 31フィールド（日付、心拍数、歩数、カロリー、ストレス、SpO2など）
- `activities`: 20フィールド（activity_id、名前、タイプ、タイミング、距離、心拍数など）
- `sleep`: 11フィールド（日付、睡眠ステージ、SpO2、呼吸数、心拍数）
- `stress`: 2フィールド（タイムスタンプ、ストレス値）
- `weight`: 7フィールド（日付、体重、BMI、体脂肪率など）
- `resting_hr`: 2フィールド（日付、安静時心拍数）

## 主な設計上の決定事項

1. **2つの同期モード**: incremental（追加）とfull_refresh（置換）をサポート
2. **空テーブルの作成**: データが存在しない場合、スキーマ付きの空テーブルを作成
3. **ラッパーパターン**: `garmindb_wrapper.py`は上流のGarminDBライブラリのTypeErrorを修正するために存在
4. **グレースフルデグラデーション**: Garminインポートが失敗してもDBが存在する場合、ワークフローはキャッシュされたデータを同期
5. **テーブル名の検証**: `validate_table_name()`でSQLインジェクションを防止
