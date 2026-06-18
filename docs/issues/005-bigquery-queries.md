# Issue #5: BigQuery専用クエリ実装

## 📋 概要
BigQueryの高度な機能（ウィンドウ関数、標準SQL）を活用した効率的なCO2分析クエリを実装する

## 🎯 目標
- BigQuery標準SQLの活用
- ウィンドウ関数による高度な分析
- パフォーマンス最適化
- 複雑な時系列分析

## 📝 詳細要件

### 実装するクエリ群

#### 1. 高精度CO2トレンド分析
```sql
WITH co2_with_trends AS (
  SELECT 
    datetime,
    co2,
    temperature,
    -- 移動平均（10分）
    AVG(co2) OVER (
      ORDER BY datetime 
      ROWS BETWEEN 9 PRECEDING AND CURRENT ROW
    ) as moving_avg_10min,
    
    -- 前回値との差分
    co2 - LAG(co2, 1) OVER (ORDER BY datetime) as co2_change,
    
    -- 1時間前との比較
    co2 - LAG(co2, 60) OVER (ORDER BY datetime) as co2_change_1h,
    
    -- 急激な変化の検出（5分間で100ppm以上）
    CASE 
      WHEN co2 - LAG(co2, 5) OVER (ORDER BY datetime) > 100 THEN 'RAPID_INCREASE'
      WHEN LAG(co2, 5) OVER (ORDER BY datetime) - co2 > 100 THEN 'RAPID_DECREASE'
      ELSE 'NORMAL'
    END as change_type
    
  FROM `monitoring-bedroom.room_temperature.bedroom_co2`
  WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
  ORDER BY datetime
)
SELECT * FROM co2_with_trends
ORDER BY datetime DESC
```

#### 2. CO2濃度分布分析
```sql
WITH co2_distribution AS (
  SELECT 
    EXTRACT(HOUR FROM datetime) as hour_of_day,
    
    -- 時間帯別統計
    AVG(co2) as avg_co2,
    STDDEV(co2) as stddev_co2,
    MIN(co2) as min_co2,
    MAX(co2) as max_co2,
    
    -- パーセンタイル
    PERCENTILE_CONT(co2, 0.5) OVER (PARTITION BY EXTRACT(HOUR FROM datetime)) as median_co2,
    PERCENTILE_CONT(co2, 0.95) OVER (PARTITION BY EXTRACT(HOUR FROM datetime)) as p95_co2,
    
    -- 閾値超過率
    COUNTIF(co2 > 800) / COUNT(*) * 100 as high_co2_rate,
    COUNTIF(co2 > 1200) / COUNT(*) * 100 as danger_co2_rate
    
  FROM `monitoring-bedroom.room_temperature.bedroom_co2`
  WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL @days DAY)
  GROUP BY hour_of_day
)
SELECT * FROM co2_distribution
ORDER BY hour_of_day
```

#### 3. 換気効果分析
```sql
WITH ventilation_analysis AS (
  SELECT 
    datetime,
    co2,
    temperature,
    
    -- CO2減少期間の検出
    CASE 
      WHEN co2 < LAG(co2, 1) OVER (ORDER BY datetime) 
       AND LAG(co2, 1) OVER (ORDER BY datetime) < LAG(co2, 2) OVER (ORDER BY datetime)
      THEN 1 ELSE 0 
    END as is_decreasing,
    
    -- 減少率の計算
    CASE 
      WHEN LAG(co2, 1) OVER (ORDER BY datetime) > 0
      THEN (LAG(co2, 1) OVER (ORDER BY datetime) - co2) / LAG(co2, 1) OVER (ORDER BY datetime) * 100
      ELSE 0
    END as decrease_rate_percent,
    
    -- 連続減少時間の計算
    SUM(CASE WHEN co2 < LAG(co2, 1) OVER (ORDER BY datetime) THEN 1 ELSE 0 END) 
      OVER (ORDER BY datetime ROWS BETWEEN CURRENT ROW AND 30 FOLLOWING) as consecutive_decrease_minutes
    
  FROM `monitoring-bedroom.room_temperature.bedroom_co2`
  WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
)
SELECT * FROM ventilation_analysis
WHERE is_decreasing = 1 OR decrease_rate_percent > 5
ORDER BY datetime DESC
```

#### 4. 異常検知クエリ
```sql
WITH anomaly_detection AS (
  SELECT 
    datetime,
    co2,
    temperature,
    
    -- 統計的異常値検出（Z-score）
    (co2 - AVG(co2) OVER (ORDER BY datetime ROWS BETWEEN 120 PRECEDING AND CURRENT ROW)) 
    / STDDEV(co2) OVER (ORDER BY datetime ROWS BETWEEN 120 PRECEDING AND CURRENT ROW) as z_score,
    
    -- 季節性を考慮した異常検知（時間帯別）
    ABS(co2 - AVG(co2) OVER (
      PARTITION BY EXTRACT(HOUR FROM datetime) 
      ORDER BY datetime ROWS BETWEEN 60 PRECEDING AND CURRENT ROW
    )) as hourly_deviation,
    
    -- 急激な変化の検知
    ABS(co2 - LAG(co2, 1) OVER (ORDER BY datetime)) as sudden_change,
    
    -- 異常フラグ
    CASE 
      WHEN ABS((co2 - AVG(co2) OVER (ORDER BY datetime ROWS BETWEEN 120 PRECEDING AND CURRENT ROW)) 
           / STDDEV(co2) OVER (ORDER BY datetime ROWS BETWEEN 120 PRECEDING AND CURRENT ROW)) > 2 
      THEN 'STATISTICAL_ANOMALY'
      
      WHEN ABS(co2 - LAG(co2, 1) OVER (ORDER BY datetime)) > 200 
      THEN 'SUDDEN_CHANGE'
      
      WHEN co2 > 1500 
      THEN 'EXTREME_VALUE'
      
      ELSE 'NORMAL'
    END as anomaly_type
    
  FROM `monitoring-bedroom.room_temperature.bedroom_co2`
  WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
)
SELECT * FROM anomaly_detection
WHERE anomaly_type != 'NORMAL'
ORDER BY datetime DESC
```

#### 5. 予測分析クエリ
```sql
WITH prediction_data AS (
  SELECT 
    datetime,
    co2,
    temperature,
    
    -- 線形回帰による予測（簡易版）
    REGR_SLOPE(co2, UNIX_SECONDS(datetime)) OVER (
      ORDER BY datetime ROWS BETWEEN 60 PRECEDING AND CURRENT ROW
    ) as co2_trend_slope,
    
    REGR_INTERCEPT(co2, UNIX_SECONDS(datetime)) OVER (
      ORDER BY datetime ROWS BETWEEN 60 PRECEDING AND CURRENT ROW
    ) as co2_trend_intercept,
    
    -- 30分後の予測値
    REGR_SLOPE(co2, UNIX_SECONDS(datetime)) OVER (
      ORDER BY datetime ROWS BETWEEN 60 PRECEDING AND CURRENT ROW
    ) * (UNIX_SECONDS(datetime) + 1800) + 
    REGR_INTERCEPT(co2, UNIX_SECONDS(datetime)) OVER (
      ORDER BY datetime ROWS BETWEEN 60 PRECEDING AND CURRENT ROW
    ) as predicted_co2_30min
    
  FROM `monitoring-bedroom.room_temperature.bedroom_co2`
  WHERE datetime >= DATETIME_SUB(CURRENT_TIMESTAMP(), INTERVAL @hours HOUR)
)
SELECT 
  datetime,
  co2,
  predicted_co2_30min,
  CASE 
    WHEN predicted_co2_30min > 1200 THEN 'WILL_EXCEED_DANGER'
    WHEN predicted_co2_30min > 800 THEN 'WILL_EXCEED_CAUTION'
    ELSE 'WILL_BE_NORMAL'
  END as prediction_status
FROM prediction_data
ORDER BY datetime DESC
LIMIT 1
```

## ✅ 完了条件
- [ ] 全5つのクエリパターンの実装
- [ ] パラメータ化（@hours, @days）
- [ ] エラーハンドリング
- [ ] パフォーマンステスト
- [ ] BigQuery課金最適化
- [ ] ドキュメント化

## 🧪 テスト内容
```python
async def test_trend_analysis_query():
    accessor = AirQualityDatabaseAccessor(settings)
    result = await accessor.execute_bigquery_trend_analysis(hours=3)
    
    assert len(result) > 0
    assert "moving_avg_10min" in result[0]
    assert "change_type" in result[0]

async def test_distribution_analysis():
    result = await accessor.execute_bigquery_distribution_analysis(days=7)
    
    # 24時間分のデータ
    assert len(result) == 24
    assert all("avg_co2" in row for row in result)

async def test_anomaly_detection():
    result = await accessor.execute_bigquery_anomaly_detection(hours=6)
    
    for row in result:
        assert row["anomaly_type"] in [
            'STATISTICAL_ANOMALY', 
            'SUDDEN_CHANGE', 
            'EXTREME_VALUE'
        ]

async def test_prediction_query():
    result = await accessor.execute_bigquery_prediction(hours=2)
    
    assert "predicted_co2_30min" in result[0]
    assert "prediction_status" in result[0]
```

## 📁 ファイル構成
```
src/database/
├── bigquery_queries.py     # 新規作成
├── air_quality_accessor.py # 更新（BigQueryクエリ統合）
└── __init__.py
tests/
└── test_bigquery_queries.py # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #4 AirQualityDatabaseAccessor実装
- 次のIssue: #6 CO2分析ロジック実装

## ⚡ BigQuery最適化
- **課金効率**: 必要なカラムのみSELECT
- **パーティション**: datetimeカラムでの効率的検索
- **ウィンドウ枠**: 適切なROWSまたはRANGE指定
- **キャッシュ**: 同一クエリの結果キャッシュ活用

## 🎯 分析の価値
- **リアルタイム監視**: 異常検知による即座のアラート
- **パターン発見**: 時間帯別のCO2変動パターン
- **予測機能**: 30分後の状態予測で先回りした換気
- **効果測定**: 換気行動の効果を定量的に評価