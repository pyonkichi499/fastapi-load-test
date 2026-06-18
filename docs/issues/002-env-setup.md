# Issue #2: 環境設定とテーブルアクセス確認

## 📋 概要
BigQueryの実テーブル `room_temperature.bedroom_co2` へのアクセスを確認し、環境設定を整備する

## 🎯 目標
- 実際のテーブルへの接続確認
- 環境変数の設定
- データ構造の確認
- 設定クラスの実装

## 📝 詳細要件

### 設定クラス
```python
class AirQualitySettings(BaseSettings):
    PROJECT_ID: str = "monitoring-bedroom"
    BIGQUERY_DATASET: str = "room_temperature"
    BIGQUERY_TABLE: str = "bedroom_co2"
    
    # ローカル開発用
    USE_BIGQUERY: bool = True
    SQLITE_PATH: str = "co2_data.db"
```

### 確認すべき項目
- テーブルスキーマの取得
- 最新データの確認
- データ件数の確認
- 日時範囲の確認

### 環境設定
```bash
# .env ファイル
PROJECT_ID=monitoring-bedroom
BIGQUERY_DATASET=room_temperature
BIGQUERY_TABLE=bedroom_co2
USE_BIGQUERY=true
```

## ✅ 完了条件
- [ ] 実テーブルへの接続確認
- [ ] テーブルスキーマの確認
- [ ] 最新データの取得確認
- [ ] 設定クラスの実装
- [ ] .envファイルの設定

## 🧪 テスト内容
```python
async def test_table_access():
    settings = AirQualitySettings()
    client = BigQueryClient(settings.PROJECT_ID)
    
    # テーブル存在確認
    query = f"SELECT COUNT(*) as count FROM `{settings.PROJECT_ID}.{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}` LIMIT 1"
    result = await client.execute_query(query)
    assert result[0]["count"] >= 0

async def test_latest_data():
    # 最新データの取得テスト
    query = """
    SELECT datetime, temperature, co2
    FROM `monitoring-bedroom.room_temperature.bedroom_co2`
    ORDER BY datetime DESC
    LIMIT 5
    """
    result = await client.execute_query(query)
    assert len(result) > 0
    assert "datetime" in result[0]
    assert "co2" in result[0]
```

## 📊 確認すべきデータ
```sql
-- スキーマ確認
SELECT column_name, data_type, is_nullable
FROM `monitoring-bedroom.room_temperature.INFORMATION_SCHEMA.COLUMNS`
WHERE table_name = 'bedroom_co2';

-- データサンプル
SELECT datetime, temperature, co2, data
FROM `monitoring-bedroom.room_temperature.bedroom_co2`
ORDER BY datetime DESC
LIMIT 10;

-- データ範囲確認
SELECT 
  MIN(datetime) as earliest,
  MAX(datetime) as latest,
  COUNT(*) as total_records
FROM `monitoring-bedroom.room_temperature.bedroom_co2`;
```

## 📁 ファイル構成
```
src/database/
├── bigquery_client.py
├── air_quality_config.py  # 新規作成
└── __init__.py
.env  # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #1 BigQuery接続ライブラリの実装
- 次のIssue: #3 ローカル開発用SQLiteセットアップ

## ⚠️ 注意事項
- 本番データのため、クエリ実行は慎重に
- 大量データ取得を避ける（LIMIT使用）
- BigQueryの課金に注意