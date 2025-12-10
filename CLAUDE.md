# CLAUDE.md

Claude Code 用のプロジェクトガイド。

## コマンド

```bash
pip install -r requirements.txt
python garmindb_wrapper.py --download --import --analyze --latest
python sync_bq.py  # GCP_PROJECT_ID 環境変数が必要
```

## 構成

```
Garmin Connect API → garmindb_wrapper.py → ~/HealthData/DBs/*.db → sync_bq.py → BigQuery
```

## ファイル

| ファイル | 役割 |
|---------|------|
| `sync_bq.py` | SQLite → BigQuery 同期。MERGE で重複防止 |
| `garmindb_wrapper.py` | GarminDB CLI ラッパー。stats=None の TypeError 回避 |
| `.github/workflows/sync.yml` | 毎日 UTC 21:00 に実行 |

## 同期モード

- **incremental**: 30日分取得、MERGE で同期
- **full_refresh**: 2015年から全取得、テーブル置換

## 主キー

| テーブル | 主キー |
|---------|--------|
| daily_summary, sleep, weight, resting_hr | day |
| activities | activity_id |
| stress | timestamp |
