# Issue #4: AirQualityDatabaseAccessor実装

## 📋 概要
CO2データ分析に特化したデータベースアクセサーを実装し、ビジネスロジックとデータアクセスを分離する

## 🎯 目標
- CO2分析に特化したメソッドの実装
- BigQuery/SQLite両対応
- 効率的なクエリ設計
- エラーハンドリング

## 📝 詳細要件

### 実装するクラス
```python
class AirQualityDatabaseAccessor:
    def __init__(self, settings: AirQualitySettings):
        self.manager = DatabaseManager(settings)
        self.table_name = f"{settings.BIGQUERY_DATASET}.{settings.BIGQUERY_TABLE}"
    
    async def get_latest_reading(self) -> Dict[str, Any]:
        """最新の測定値を取得"""
    
    async def get_readings_by_hours(self, hours: int) -> List[Dict[str, Any]]:
        """指定時間分のデータを取得"""
    
    async def get_co2_statistics(self, hours: int) -> Dict[str, float]:
        """CO2統計を計算"""
    
    async def get_high_co2_periods(self, hours: int, threshold: int = 800) -> List[Dict]:
        """高CO2期間を分析"""
    
    async def calculate_co2_trend(self, hours: int) -> Dict[str, Any]:
        """CO2トレンドを計算"""
```

### 実装メソッド詳細

#### 1. 最新値取得
```python
async def get_latest_reading(self) -> Dict[str, Any]:
    query = f"""
    SELECT datetime, temperature, co2, data
    FROM {self.table_name}
    ORDER BY datetime DESC
    LIMIT 1
    """
    results = await self.manager.execute_query(query)
    if not results:
        raise NoDataFoundError("No readings available")
    return results[0]
```

#### 2. 期間データ取得
```python
async def get_readings_by_hours(self, hours: int) -> List[Dict[str, Any]]:
    # BigQuery用
    bigquery_query = f"""
    SELECT datetime, temperature, co2
    FROM {self.table_name}
    WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
    ORDER BY datetime ASC
    """
    
    # SQLite用
    sqlite_query = f"""
    SELECT datetime, temperature, co2
    FROM bedroom_co2
    WHERE datetime >= datetime('now', '-{hours} hours')
    ORDER BY datetime ASC
    """
```

#### 3. CO2統計計算
```python
async def get_co2_statistics(self, hours: int) -> Dict[str, float]:
    query = f"""
    SELECT 
        AVG(co2) as avg_co2,
        MAX(co2) as max_co2,
        MIN(co2) as min_co2,
        COUNT(*) as data_points
    FROM {self.table_name}
    WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
    """
    # 返り値: {"avg_co2": 750.5, "max_co2": 1200, "min_co2": 450, "data_points": 180}
```

#### 4. 高CO2期間分析
```python
async def get_high_co2_periods(self, hours: int, threshold: int = 800) -> List[Dict]:
    """連続する高CO2期間を検出"""
    # 複雑なウィンドウ関数を使用
    query = f"""
    WITH co2_flags AS (
        SELECT 
            datetime,
            co2,
            CASE WHEN co2 >= {threshold} THEN 1 ELSE 0 END as is_high
        FROM {self.table_name}
        WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours} HOUR)
        ORDER BY datetime
    ),
    grouped_periods AS (
        SELECT 
            datetime,
            co2,
            is_high,
            SUM(CASE WHEN is_high != LAG(is_high, 1, 0) OVER (ORDER BY datetime) 
                     THEN 1 ELSE 0 END) 
                OVER (ORDER BY datetime) as group_id
        FROM co2_flags
    )
    SELECT 
        group_id,
        MIN(datetime) as start_time,
        MAX(datetime) as end_time,
        AVG(co2) as avg_co2,
        is_high
    FROM grouped_periods
    WHERE is_high = 1
    GROUP BY group_id, is_high
    ORDER BY start_time DESC
    """
```

#### 5. トレンド計算
```python
async def calculate_co2_trend(self, hours: int) -> Dict[str, Any]:
    """直近1時間と前1時間を比較してトレンドを判定"""
    query = f"""
    WITH hourly_avg AS (
        SELECT 
            CASE 
                WHEN datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR) 
                THEN 'recent'
                ELSE 'previous'
            END as period,
            AVG(co2) as avg_co2
        FROM {self.table_name}
        WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL 2 HOUR)
        GROUP BY period
    )
    SELECT 
        MAX(CASE WHEN period = 'recent' THEN avg_co2 END) as recent_avg,
        MAX(CASE WHEN period = 'previous' THEN avg_co2 END) as previous_avg
    FROM hourly_avg
    """
    
    # トレンド判定ロジック
    # difference = recent_avg - previous_avg
    # if difference > 50: return "急上昇"
    # elif difference > 20: return "上昇傾向"
    # elif difference < -50: return "急下降"
    # elif difference < -20: return "下降傾向"
    # else: return "安定"
```

## ✅ 完了条件
- [ ] 全メソッドの実装
- [ ] BigQuery/SQLite両対応
- [ ] エラーハンドリング
- [ ] データ型の統一
- [ ] パフォーマンステスト
- [ ] カスタム例外クラス

## 🧪 テスト内容
```python
async def test_latest_reading():
    accessor = AirQualityDatabaseAccessor(settings)
    reading = await accessor.get_latest_reading()
    
    assert "datetime" in reading
    assert "co2" in reading
    assert "temperature" in reading
    assert isinstance(reading["co2"], int)

async def test_co2_statistics():
    accessor = AirQualityDatabaseAccessor(settings)
    stats = await accessor.get_co2_statistics(hours=3)
    
    assert "avg_co2" in stats
    assert "max_co2" in stats
    assert "min_co2" in stats
    assert stats["max_co2"] >= stats["avg_co2"] >= stats["min_co2"]

async def test_high_co2_detection():
    # 高CO2テストデータを用意
    accessor = AirQualityDatabaseAccessor(settings)
    periods = await accessor.get_high_co2_periods(hours=3, threshold=800)
    
    for period in periods:
        assert period["avg_co2"] >= 800
        assert "start_time" in period
        assert "end_time" in period

async def test_trend_calculation():
    accessor = AirQualityDatabaseAccessor(settings)
    trend = await accessor.calculate_co2_trend(hours=2)
    
    assert "trend" in trend
    assert trend["trend"] in ["急上昇", "上昇傾向", "安定", "下降傾向", "急下降"]
```

## 📁 ファイル構成
```
src/database/
├── air_quality_accessor.py  # 新規作成
├── exceptions.py           # 新規作成（カスタム例外）
└── __init__.py
tests/
└── test_air_quality_accessor.py  # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #3 ローカル開発用SQLiteセットアップ
- 次のIssue: #5 BigQuery専用クエリ実装

## ⚡ パフォーマンス考慮
- **インデックス活用**: datetimeカラムのインデックス
- **クエリ最適化**: 必要な期間のみ取得
- **キャッシュ戦略**: 頻繁にアクセスする統計データ
- **BigQuery課金**: クエリ頻度とデータ量の最適化