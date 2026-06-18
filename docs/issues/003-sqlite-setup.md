# Issue #3: ローカル開発用SQLiteセットアップ

## 📋 概要
BigQueryと同じ構造のローカル開発用SQLiteデータベースを構築し、テストデータを投入する

## 🎯 目標
- SQLiteでのテーブル作成
- BigQueryと互換性のあるスキーマ
- テストデータの生成
- 開発環境の切り替え機能

## 📝 詳細要件

### SQLiteテーブル構造
```sql
CREATE TABLE bedroom_co2 (
    datetime TIMESTAMP NOT NULL,
    temperature REAL NOT NULL,
    co2 INTEGER NOT NULL,
    data TEXT
);

CREATE INDEX idx_bedroom_co2_datetime ON bedroom_co2(datetime);
```

### テストデータ生成
```python
async def generate_test_data(hours: int = 24):
    """テスト用のCO2データを生成"""
    # 1分間隔でデータ生成
    # CO2: 400-1500ppm（現実的な範囲）
    # 温度: 20-28度
    # パターン: 時間帯による変動を模擬
```

### データベース切り替え
```python
class DatabaseManager:
    def __init__(self, settings: AirQualitySettings):
        if settings.USE_BIGQUERY:
            self.client = BigQueryClient(settings.PROJECT_ID)
        else:
            self.client = SQLiteClient(settings.SQLITE_PATH)
    
    async def execute_query(self, query: str, params: dict = None):
        return await self.client.execute_query(query, params)
```

## ✅ 完了条件
- [ ] SQLiteテーブルの作成
- [ ] テストデータ生成機能
- [ ] BigQuery/SQLiteの切り替え機能
- [ ] 24時間分のリアルなテストデータ
- [ ] クエリの互換性確認

## 🧪 テスト内容
```python
async def test_sqlite_setup():
    settings = AirQualitySettings(USE_BIGQUERY=False)
    manager = DatabaseManager(settings)
    
    # データ投入テスト
    await generate_test_data(hours=24)
    
    # データ取得テスト
    query = "SELECT COUNT(*) as count FROM bedroom_co2"
    result = await manager.execute_query(query)
    assert result[0]["count"] > 1000  # 24時間 × 60分

async def test_query_compatibility():
    # BigQueryとSQLiteで同じクエリが動作することを確認
    query = """
    SELECT datetime, temperature, co2
    FROM bedroom_co2
    ORDER BY datetime DESC
    LIMIT 5
    """
    # 両方のDBで実行して結果形式が同じことを確認
```

## 📊 生成するテストデータパターン

### CO2濃度パターン
```python
def generate_co2_pattern(hour: int, minute: int) -> int:
    """時間帯に応じたCO2濃度を生成"""
    base_co2 = 450  # ベース値
    
    # 夜間（22-6時）: 高濃度（換気不足）
    if 22 <= hour or hour <= 6:
        base_co2 += 300 + random.randint(-100, 200)
    
    # 昼間（7-21時）: 中濃度
    else:
        base_co2 += 150 + random.randint(-50, 100)
    
    # 分単位の微細な変動
    base_co2 += random.randint(-20, 20)
    
    return max(400, min(1500, base_co2))
```

### 温度パターン
```python
def generate_temperature_pattern(hour: int) -> float:
    """時間帯に応じた温度を生成"""
    # 日内変動を模擬
    base_temp = 23.0 + 3 * math.sin((hour - 6) * math.pi / 12)
    return round(base_temp + random.uniform(-1.0, 1.0), 1)
```

## 📁 ファイル構成
```
src/database/
├── bigquery_client.py
├── sqlite_client.py      # 新規作成
├── database_manager.py   # 新規作成
├── test_data_generator.py # 新規作成
└── __init__.py
tests/
└── test_database_setup.py # 新規作成
co2_data.db               # 生成されるSQLiteファイル
```

## 🔗 関連Issue
- 前のIssue: #2 環境設定とテーブルアクセス確認
- 次のIssue: #4 AirQualityDatabaseAccessor実装

## 💡 テストデータの特徴
- **現実的なパターン**: 実際のCO2変動を模擬
- **異常値**: 1200ppm超えの「要換気」状態を含む
- **トレンド**: 徐々に上昇/下降するパターン
- **ノイズ**: センサーの誤差を模擬した微細な変動