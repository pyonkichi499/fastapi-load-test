# 温度変化予測API実装手順

## 概要
過去の温度パターンから、次の1時間の温度変化を予測するAPIです。移動平均とトレンド分析を使用した簡易的な予測を行います。

## ブランチ作成
```bash
git checkout develop
git pull origin develop
git checkout -b feature/api-temperature-predict
```

## 実装手順

### 1. レスポンスモデルの作成
`src/openapi_server/models/temperature_prediction.py`:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class TemperatureDataPoint(BaseModel):
    timestamp: datetime
    temperature: float
    is_historical: bool  # True: 実データ, False: 予測データ

class TrendAnalysis(BaseModel):
    trend_direction: str  # "rising", "falling", "stable"
    rate_of_change: float  # 度/時間
    volatility: float  # 変動性（標準偏差）
    daily_pattern_detected: bool  # 日次パターンの有無

class PredictionMetadata(BaseModel):
    confidence_level: float  # 予測信頼度（0-100）
    method_used: str  # 使用した予測手法
    factors_considered: List[str]  # 考慮した要因

class TemperaturePredictionResponse(BaseModel):
    room_name: str
    current_temperature: float
    predicted_temperature: float  # 1時間後の予測温度
    temperature_range: dict  # {"min": float, "max": float}
    historical_data: List[TemperatureDataPoint]
    predicted_data: List[TemperatureDataPoint]  # 15分間隔の予測
    trend_analysis: TrendAnalysis
    metadata: PredictionMetadata
    recommendations: List[str]
```

### 2. API実装クラスの作成
`src/openapi_server/impl/temperature_prediction_api_impl.py`:
```python
from datetime import datetime, timedelta
from typing import List, Tuple, Optional
import statistics
import math
from fastapi import HTTPException

from openapi_server.apis.temperature_prediction_api_base import BaseTemperaturePredictionApi
from database.accessor import DatabaseAccessor
from database.config import get_db_settings
from openapi_server.models.temperature_prediction import (
    TemperaturePredictionResponse, TemperatureDataPoint, 
    TrendAnalysis, PredictionMetadata
)

class TemperaturePredictionApiImpl(BaseTemperaturePredictionApi):
    def __init__(self):
        self.settings = get_db_settings()
        self.db_accessor = DatabaseAccessor(self.settings)
    
    def calculate_moving_average(self, data: List[Tuple[datetime, float]], window_hours: int) -> List[float]:
        """移動平均を計算"""
        if len(data) < 2:
            return [data[0][1]] if data else []
        
        averages = []
        window_start = data[0][0]
        
        for current_time, _ in data:
            window_end = current_time
            window_start = current_time - timedelta(hours=window_hours)
            
            window_data = [
                temp for time, temp in data 
                if window_start <= time <= window_end
            ]
            
            if window_data:
                averages.append(statistics.mean(window_data))
            else:
                averages.append(data[0][1])  # フォールバック
        
        return averages
    
    def detect_daily_pattern(self, data: List[Tuple[datetime, float]]) -> Tuple[bool, Optional[List[float]]]:
        """日次パターンを検出（24時間周期）"""
        if len(data) < 48:  # 2日分のデータが必要
            return False, None
        
        # 時間帯別の平均温度を計算
        hourly_temps = {hour: [] for hour in range(24)}
        
        for timestamp, temp in data:
            hour = timestamp.hour
            hourly_temps[hour].append(temp)
        
        # 各時間帯の平均を計算
        hourly_averages = []
        pattern_detected = True
        
        for hour in range(24):
            if hourly_temps[hour]:
                avg = statistics.mean(hourly_temps[hour])
                hourly_averages.append(avg)
                
                # 標準偏差が大きすぎる場合はパターンなしと判定
                if len(hourly_temps[hour]) > 1:
                    std = statistics.stdev(hourly_temps[hour])
                    if std > 2.0:  # 2度以上のばらつき
                        pattern_detected = False
            else:
                hourly_averages.append(None)
                pattern_detected = False
        
        return pattern_detected, hourly_averages if pattern_detected else None
    
    def calculate_trend(self, data: List[Tuple[datetime, float]]) -> Tuple[str, float]:
        """トレンド方向と変化率を計算"""
        if len(data) < 2:
            return "stable", 0.0
        
        # 最小二乗法で線形回帰
        n = len(data)
        
        # 時間を数値に変換（最初のデータポイントからの経過時間）
        base_time = data[0][0]
        x_values = [(d[0] - base_time).total_seconds() / 3600 for d in data]  # 時間単位
        y_values = [d[1] for d in data]
        
        # 回帰係数の計算
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)
        
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)
        
        if denominator == 0:
            slope = 0
        else:
            slope = numerator / denominator
        
        # トレンド判定
        if abs(slope) < 0.1:  # 0.1度/時間未満は安定
            trend = "stable"
        elif slope > 0:
            trend = "rising"
        else:
            trend = "falling"
        
        return trend, slope
    
    def predict_temperature(
        self, 
        current_temp: float,
        historical_data: List[Tuple[datetime, float]],
        hourly_pattern: Optional[List[float]] = None,
        hours_ahead: int = 1
    ) -> Tuple[float, float, float]:
        """温度を予測（予測値、最小値、最大値）"""
        
        # 1. トレンドベースの予測
        trend_direction, rate_of_change = self.calculate_trend(historical_data[-12:])  # 直近12時間
        trend_prediction = current_temp + (rate_of_change * hours_ahead)
        
        # 2. 移動平均ベースの予測
        ma_3h = self.calculate_moving_average(historical_data, 3)
        ma_6h = self.calculate_moving_average(historical_data, 6)
        
        if ma_3h and ma_6h:
            # 短期と中期の移動平均の差から勢いを計算
            momentum = ma_3h[-1] - ma_6h[-1]
            ma_prediction = current_temp + momentum
        else:
            ma_prediction = current_temp
        
        # 3. パターンベースの予測（日次パターンがある場合）
        if hourly_pattern:
            current_hour = datetime.now().hour
            target_hour = (current_hour + hours_ahead) % 24
            
            if hourly_pattern[current_hour] and hourly_pattern[target_hour]:
                pattern_diff = hourly_pattern[target_hour] - hourly_pattern[current_hour]
                pattern_prediction = current_temp + pattern_diff
            else:
                pattern_prediction = None
        else:
            pattern_prediction = None
        
        # 予測の統合
        predictions = [p for p in [trend_prediction, ma_prediction, pattern_prediction] if p is not None]
        
        if predictions:
            final_prediction = statistics.mean(predictions)
            
            # 信頼区間の計算（簡易版）
            volatility = statistics.stdev([d[1] for d in historical_data[-24:]]) if len(historical_data) >= 24 else 1.0
            confidence_margin = volatility * 1.5  # 1.5σ
            
            min_temp = final_prediction - confidence_margin
            max_temp = final_prediction + confidence_margin
        else:
            final_prediction = current_temp
            min_temp = current_temp - 1.0
            max_temp = current_temp + 1.0
        
        return final_prediction, min_temp, max_temp
    
    def generate_recommendations(
        self, 
        current_temp: float,
        predicted_temp: float,
        trend: str
    ) -> List[str]:
        """温度変化に基づくレコメンデーション"""
        recommendations = []
        
        temp_change = predicted_temp - current_temp
        
        # 温度変化に基づくアドバイス
        if abs(temp_change) > 3:
            if temp_change > 0:
                recommendations.append(f"1時間後に{temp_change:.1f}度上昇が予想されます。冷房の準備を検討してください")
            else:
                recommendations.append(f"1時間後に{abs(temp_change):.1f}度下降が予想されます。暖房の準備を検討してください")
        
        # 予測温度に基づくアドバイス
        if predicted_temp > 28:
            recommendations.append("予測温度が高めです。熱中症対策をお忘れなく")
        elif predicted_temp < 18:
            recommendations.append("予測温度が低めです。暖かい服装を準備しましょう")
        
        # トレンドに基づくアドバイス
        if trend == "rising":
            recommendations.append("温度上昇傾向が続いています。換気を検討してください")
        elif trend == "falling":
            recommendations.append("温度下降傾向です。窓を閉めることを検討してください")
        
        if not recommendations:
            recommendations.append("温度は安定しています。快適な環境が維持されそうです")
        
        return recommendations
    
    async def predict_temperature_change(
        self,
        room_name: str,
        hours_to_predict: int = 1
    ) -> TemperaturePredictionResponse:
        """指定された部屋の温度変化を予測"""
        
        # 過去24時間のデータを取得
        try:
            records = await self.db_accessor.fetch_records(
                table_name="room_temperature",
                columns=["timestamp", "temperature"],
                filters={"room_name": room_name},
                order_by=[("timestamp", "DESC")],
                limit=288  # 24時間×12（5分間隔想定）
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        if not records:
            raise HTTPException(status_code=404, detail=f"No data found for room: {room_name}")
        
        # 時系列順に並び替え
        records.reverse()
        
        # データを扱いやすい形式に変換
        historical_data = [(r["timestamp"], r["temperature"]) for r in records]
        current_temp = historical_data[-1][1]
        
        # 日次パターンの検出
        pattern_detected, hourly_pattern = self.detect_daily_pattern(historical_data)
        
        # トレンド分析
        trend_direction, rate_of_change = self.calculate_trend(historical_data)
        volatility = statistics.stdev([d[1] for d in historical_data]) if len(historical_data) > 1 else 0.0
        
        # 温度予測
        predicted_temp, min_temp, max_temp = self.predict_temperature(
            current_temp, historical_data, hourly_pattern, hours_to_predict
        )
        
        # 15分間隔の予測データ生成
        predicted_data_points = []
        base_time = historical_data[-1][0]
        
        for i in range(1, 5):  # 15分、30分、45分、60分
            minutes_ahead = i * 15
            time_point = base_time + timedelta(minutes=minutes_ahead)
            
            # 線形補間で中間値を計算
            interpolated_temp = current_temp + (predicted_temp - current_temp) * (minutes_ahead / 60)
            
            predicted_data_points.append(TemperatureDataPoint(
                timestamp=time_point,
                temperature=interpolated_temp,
                is_historical=False
            ))
        
        # 履歴データポイント（最新24個）
        historical_data_points = [
            TemperatureDataPoint(
                timestamp=timestamp,
                temperature=temp,
                is_historical=True
            )
            for timestamp, temp in historical_data[-24:]
        ]
        
        # メタデータ生成
        factors = ["過去のトレンド", "移動平均"]
        if pattern_detected:
            factors.append("日次パターン")
        
        confidence = 70.0  # ベース信頼度
        if len(historical_data) > 48:
            confidence += 10.0
        if pattern_detected:
            confidence += 10.0
        if volatility < 1.0:
            confidence += 10.0
        
        metadata = PredictionMetadata(
            confidence_level=min(95.0, confidence),
            method_used="統合予測（トレンド＋移動平均＋パターン）",
            factors_considered=factors
        )
        
        # レコメンデーション生成
        recommendations = self.generate_recommendations(
            current_temp, predicted_temp, trend_direction
        )
        
        return TemperaturePredictionResponse(
            room_name=room_name,
            current_temperature=current_temp,
            predicted_temperature=predicted_temp,
            temperature_range={"min": min_temp, "max": max_temp},
            historical_data=historical_data_points,
            predicted_data=predicted_data_points,
            trend_analysis=TrendAnalysis(
                trend_direction=trend_direction,
                rate_of_change=rate_of_change,
                volatility=volatility,
                daily_pattern_detected=pattern_detected
            ),
            metadata=metadata,
            recommendations=recommendations
        )
```

### 3. APIルートの追加
`src/openapi_server/apis/temperature_prediction_api.py`:
```python
from fastapi import APIRouter, Query, Path

from openapi_server.impl.temperature_prediction_api_impl import TemperaturePredictionApiImpl
from openapi_server.models.temperature_prediction import TemperaturePredictionResponse

router = APIRouter(prefix="/api/temperature", tags=["temperature"])
api_impl = TemperaturePredictionApiImpl()

@router.get("/predict/{room_name}", response_model=TemperaturePredictionResponse)
async def predict_temperature_change(
    room_name: str = Path(..., description="部屋の名前"),
    hours_to_predict: int = Query(1, description="予測時間（時間）", ge=1, le=3)
):
    """指定された部屋の温度変化を予測します"""
    return await api_impl.predict_temperature_change(
        room_name=room_name,
        hours_to_predict=hours_to_predict
    )
```

### 4. main.pyへのルート登録
`src/openapi_server/main.py`に追加:
```python
from openapi_server.apis import temperature_prediction_api

# 既存のルーター登録に追加
app.include_router(temperature_prediction_api.router)
```

### 5. テストの作成
`tests/test_temperature_prediction_api.py`:
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from openapi_server.impl.temperature_prediction_api_impl import TemperaturePredictionApiImpl

@pytest.mark.asyncio
async def test_calculate_trend():
    api = TemperaturePredictionApiImpl()
    
    # 上昇トレンドのデータ
    now = datetime.now()
    rising_data = [
        (now - timedelta(hours=i), 20.0 + i * 0.5)
        for i in range(10, 0, -1)
    ]
    
    trend, rate = api.calculate_trend(rising_data)
    assert trend == "rising"
    assert rate > 0
    
    # 安定したデータ
    stable_data = [
        (now - timedelta(hours=i), 22.0 + (i % 2) * 0.1)
        for i in range(10, 0, -1)
    ]
    
    trend, rate = api.calculate_trend(stable_data)
    assert trend == "stable"
    assert abs(rate) < 0.1

@pytest.mark.asyncio
async def test_detect_daily_pattern():
    api = TemperaturePredictionApiImpl()
    
    # 明確な日次パターンを持つデータ
    now = datetime.now()
    pattern_data = []
    
    for day in range(3):
        for hour in range(24):
            timestamp = now - timedelta(days=day, hours=23-hour)
            # 朝は低く、昼は高い温度パターン
            if 6 <= hour <= 18:
                temp = 25.0 + (hour - 6) * 0.5
            else:
                temp = 20.0
            pattern_data.append((timestamp, temp))
    
    detected, pattern = api.detect_daily_pattern(pattern_data)
    assert detected is True
    assert pattern is not None

@pytest.mark.asyncio
async def test_predict_temperature_change():
    api = TemperaturePredictionApiImpl()
    
    # モックデータ：温度上昇トレンド
    now = datetime.now()
    mock_records = []
    
    for i in range(48, 0, -1):
        mock_records.append({
            "timestamp": now - timedelta(hours=i/2),
            "temperature": 20.0 + (48-i) * 0.1  # 緩やかな上昇
        })
    
    with patch.object(api.db_accessor, 'fetch_records', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_records
        
        response = await api.predict_temperature_change("test_room", hours_to_predict=1)
        
        assert response.room_name == "test_room"
        assert response.predicted_temperature > response.current_temperature
        assert response.trend_analysis.trend_direction == "rising"
        assert len(response.predicted_data) == 4  # 15分間隔×4
        assert response.metadata.confidence_level > 50
        assert len(response.recommendations) > 0
```

### 6. 動作確認
```bash
# サーバー起動
cd output
uvicorn src.openapi_server.main:app --reload

# 別ターミナルでテスト
curl http://localhost:8000/api/temperature/predict/living_room

# Swagger UIで確認
open http://localhost:8000/docs
```

### 7. テーブルへのサンプルデータ投入
```sql
-- 日次パターンを持つ温度データ（3日分）
DO $$
DECLARE
    day_offset INTEGER;
    hour_offset INTEGER;
    base_temp DECIMAL;
    temp_variation DECIMAL;
    timestamp_val TIMESTAMP;
BEGIN
    FOR day_offset IN 0..2 LOOP
        FOR hour_offset IN 0..23 LOOP
            timestamp_val := NOW() - (day_offset * INTERVAL '1 day') - (hour_offset * INTERVAL '1 hour');
            
            -- 基本温度：朝は低く、昼は高い
            IF hour_offset >= 6 AND hour_offset <= 18 THEN
                base_temp := 20 + (hour_offset - 6) * 0.5;
            ELSE
                base_temp := 18;
            END IF;
            
            -- ランダムな変動を追加
            temp_variation := (RANDOM() - 0.5) * 1.0;
            
            -- 5分間隔でデータを挿入
            FOR minute_offset IN 0..11 LOOP
                INSERT INTO room_temperature (timestamp, room_name, temperature, humidity)
                VALUES (
                    timestamp_val - (minute_offset * INTERVAL '5 minutes'),
                    'prediction_room',
                    base_temp + temp_variation,
                    50 + (RANDOM() * 20)
                );
            END LOOP;
        END LOOP;
    END LOOP;
END $$;
```

## コミットとプルリクエスト
```bash
# テスト実行
pytest tests/test_temperature_prediction_api.py

# コミット
git add .
git commit -m "feat: 温度変化予測APIを実装

- トレンド分析と移動平均による予測
- 日次パターン検出機能
- 15分間隔の詳細予測
- 信頼度とレコメンデーション生成"

# プッシュとPR作成
git push origin feature/api-temperature-predict
```

## 学習ポイント
1. **時系列分析**
   - 移動平均の実装
   - 線形回帰によるトレンド分析
   - パターン検出アルゴリズム

2. **予測モデル**
   - 複数の予測手法の統合
   - 信頼度の計算
   - 予測区間の設定

3. **FastAPI応用**
   - 複雑なレスポンスモデル
   - メタデータの提供

## 注意事項
- 実際の予測にはより高度な手法（ARIMA、機械学習）が有効
- 外部要因（天気、人の活動）を考慮するとより精度が向上