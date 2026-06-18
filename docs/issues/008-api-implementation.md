# Issue #8: CO2ステータスAPI実装

## 📋 概要
FastAPIを使用してCO2空気質分析APIのエンドポイントを実装し、全ての機能を統合する

## 🎯 目標
- FastAPIエンドポイントの実装
- 既存コンポーネントの統合
- エラーハンドリング
- ログ機能の実装

## 📝 詳細要件

### APIエンドポイント実装

#### 1. メインエンドポイント
```python
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
import logging
from typing import Optional

from openapi_server.models.air_quality import (
    AirQualityResponse, AirQualityQueryParams, ErrorResponse
)
from analysis.co2_analysis_engine import CO2AnalysisEngine
from database.air_quality_accessor import AirQualityDatabaseAccessor
from database.air_quality_config import AirQualitySettings

router = APIRouter(prefix=\"/api/air-quality\", tags=[\"air-quality\"])
logger = logging.getLogger(__name__)

# 依存性注入
def get_settings() -> AirQualitySettings:
    return AirQualitySettings()

def get_db_accessor(settings: AirQualitySettings = Depends(get_settings)) -> AirQualityDatabaseAccessor:
    return AirQualityDatabaseAccessor(settings)

def get_analysis_engine() -> CO2AnalysisEngine:
    return CO2AnalysisEngine()

@router.get(\"/co2-status\", response_model=AirQualityResponse)
async def get_co2_status(
    hours: int = Query(3, description=\"分析期間（時間）\", ge=1, le=168),
    include_timeline: bool = Query(True, description=\"時系列データを含めるか\"),
    timeline_resolution: str = Query(\"5min\", description=\"時系列データの解像度\"),
    include_predictions: bool = Query(False, description=\"予測データを含めるか\"),
    db_accessor: AirQualityDatabaseAccessor = Depends(get_db_accessor),
    analysis_engine: CO2AnalysisEngine = Depends(get_analysis_engine)
):
    \"\"\"
    CO2濃度に基づく空気質ステータスを取得
    
    現在のCO2濃度、トレンド分析、換気推奨を含む包括的な空気質情報を提供します。
    \"\"\"
    
    try:
        logger.info(f\"CO2 status request: hours={hours}, include_timeline={include_timeline}\")
        
        # パラメータバリデーション
        if hours > 24 and hours % 24 != 0:
            raise HTTPException(
                status_code=400,
                detail=\"Hours > 24 must be multiple of 24\"
            )
        
        # 分析実行
        result = await analysis_engine.analyze_air_quality(
            hours=hours,
            include_timeline=include_timeline,
            timeline_resolution=timeline_resolution,
            include_predictions=include_predictions
        )
        
        logger.info(f\"Analysis completed: status={result.status}, co2={result.current.co2}\")
        return result
        
    except ValueError as e:
        logger.error(f\"Validation error: {str(e)}\")
        raise HTTPException(status_code=400, detail=str(e))
    
    except Exception as e:
        logger.error(f\"Internal error in CO2 status: {str(e)}\", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=\"Internal server error occurred while analyzing air quality\"
        )
```

#### 2. ヘルスチェックエンドポイント
```python
from openapi_server.models.health import SystemHealth
import time
import os

# アプリケーション開始時刻
app_start_time = time.time()

@router.get(\"/health\", response_model=SystemHealth)
async def health_check(
    db_accessor: AirQualityDatabaseAccessor = Depends(get_db_accessor)
):
    \"\"\"
    システムヘルスチェック
    
    データベース接続状態とデータの新しさを確認します。
    \"\"\"
    
    try:
        # データベース接続テスト
        latest_reading = await db_accessor.get_latest_reading()
        database_status = \"connected\"
        last_data_timestamp = latest_reading.get('datetime') if latest_reading else None
        
        # データの新しさチェック
        if last_data_timestamp:
            from datetime import datetime
            data_age = (datetime.now() - last_data_timestamp).total_seconds() / 60
            data_freshness_minutes = int(data_age)
        else:
            data_freshness_minutes = None
        
        # システム状態判定
        if data_freshness_minutes and data_freshness_minutes > 10:
            status = \"degraded\"  # データが10分以上古い
        elif database_status != \"connected\":
            status = \"unhealthy\"
        else:
            status = \"healthy\"
        
    except Exception as e:
        logger.error(f\"Health check failed: {str(e)}\")
        database_status = \"error\"
        last_data_timestamp = None
        data_freshness_minutes = None
        status = \"unhealthy\"
    
    return SystemHealth(
        status=status,
        database_status=database_status,
        last_data_timestamp=last_data_timestamp,
        data_freshness_minutes=data_freshness_minutes,
        version=os.getenv(\"API_VERSION\", \"1.0.0\"),
        uptime_seconds=int(time.time() - app_start_time)
    )
```

#### 3. 統計情報エンドポイント
```python
@router.get(\"/co2-statistics\")
async def get_co2_statistics(
    hours: int = Query(24, description=\"統計期間（時間）\", ge=1, le=168),
    db_accessor: AirQualityDatabaseAccessor = Depends(get_db_accessor)
):
    \"\"\"
    CO2統計情報を取得
    
    指定期間のCO2濃度統計データを提供します。
    \"\"\"
    
    try:
        stats = await db_accessor.get_co2_statistics(hours=hours)
        
        return {
            \"period_hours\": hours,
            \"statistics\": stats,
            \"generated_at\": datetime.now()
        }
        
    except Exception as e:
        logger.error(f\"Error getting CO2 statistics: {str(e)}\")
        raise HTTPException(status_code=500, detail=\"Failed to retrieve statistics\")
```

### 実装クラス統合

#### 1. API実装クラス
```python
class AirQualityApiImpl:
    \"\"\"空気質API実装クラス\"\"\"
    
    def __init__(
        self,
        db_accessor: AirQualityDatabaseAccessor,
        analysis_engine: CO2AnalysisEngine
    ):
        self.db_accessor = db_accessor
        self.analysis_engine = analysis_engine
        self.logger = logging.getLogger(self.__class__.__name__)
    
    async def get_air_quality_status(
        self,
        params: AirQualityQueryParams
    ) -> AirQualityResponse:
        \"\"\"空気質ステータス取得のメイン処理\"\"\"
        
        try:
            # 1. 最新データ取得
            latest_reading = await self.db_accessor.get_latest_reading()
            
            # 2. 期間データ取得
            readings = await self.db_accessor.get_readings_by_hours(params.hours)
            
            # 3. 統計計算
            statistics = await self.db_accessor.get_co2_statistics(params.hours)
            
            # 4. トレンド分析
            trend_analysis = await self.analysis_engine.calculate_trend(readings)
            
            # 5. 高CO2期間計算
            high_co2_duration = self.analysis_engine.calculate_high_co2_duration(readings)
            
            # 6. 状態判定
            status = self.analysis_engine.determine_status(
                latest_reading['co2'],
                {
                    'high_co2_duration_minutes': high_co2_duration,
                    'trend': trend_analysis['trend'],
                    'co2_change_1h': trend_analysis.get('change_amount', 0)
                }
            )
            
            # 7. メッセージ生成
            message = self.analysis_engine.generate_message(status, {
                'current_co2': latest_reading['co2'],
                'trend': trend_analysis['trend'],
                'high_co2_duration_minutes': high_co2_duration
            })
            
            # 8. 推奨アクション生成
            recommendations = self.analysis_engine.generate_recommendations(
                status, {
                    'current_co2': latest_reading['co2'],
                    'current_temperature': latest_reading['temperature'],
                    'trend': trend_analysis['trend']
                }
            )
            
            # 9. アクション判定
            if status == \"危険\":
                action = \"即座に換気\"
            elif status == \"注意\":
                action = \"換気推奨\"
            else:
                action = \"問題なし\"
            
            # 10. 時系列データ準備（オプション）
            timeline = None
            if params.include_timeline:
                timeline = self._prepare_timeline_data(
                    readings, 
                    params.timeline_resolution
                )
            
            # 11. レスポンス構築
            return AirQualityResponse(
                status=status,
                current=CurrentReading(
                    co2=latest_reading['co2'],
                    temperature=latest_reading['temperature'],
                    timestamp=latest_reading['datetime']
                ),
                analysis=AnalysisData(
                    period_hours=params.hours,
                    avg_co2=statistics['avg_co2'],
                    max_co2=statistics['max_co2'],
                    min_co2=statistics['min_co2'],
                    trend=trend_analysis['trend'],
                    high_co2_duration_minutes=high_co2_duration,
                    data_points=len(readings),
                    predicted_co2_30min=trend_analysis.get('predicted_co2_30min'),
                    trend_confidence=trend_analysis.get('trend_confidence')
                ),
                message=message,
                action=action,
                recommendations=recommendations,
                timeline=timeline
            )
            
        except Exception as e:
            self.logger.error(f\"Error in get_air_quality_status: {str(e)}\", exc_info=True)
            raise
    
    def _prepare_timeline_data(
        self, 
        readings: List[Dict], 
        resolution: str
    ) -> List[TimelinePoint]:
        \"\"\"時系列データの準備\"\"\"
        
        # 解像度に応じてデータを間引き
        if resolution == \"1min\":
            step = 1
        elif resolution == \"5min\":
            step = 5
        elif resolution == \"10min\":
            step = 10
        elif resolution == \"30min\":
            step = 30
        else:
            step = 5  # デフォルト
        
        timeline = []
        for i, reading in enumerate(readings[::step]):
            timeline_point = TimelinePoint(
                timestamp=reading['datetime'],
                co2=reading['co2'],
                temperature=reading['temperature']
            )
            
            # 移動平均などの追加計算（オプション）
            if i >= 10:  # 10分移動平均
                recent_readings = readings[max(0, i-9):i+1]
                timeline_point.moving_avg_10min = sum(
                    r['co2'] for r in recent_readings
                ) / len(recent_readings)
            
            timeline.append(timeline_point)
        
        return timeline
```

### エラーハンドリング

#### 1. カスタム例外ハンドラー
```python
from fastapi import Request
from fastapi.responses import JSONResponse

@router.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content=ErrorResponse(
            error=ErrorDetail(
                code=\"VALIDATION_ERROR\",
                message=str(exc),
                details={\"request_path\": str(request.url.path)}
            )
        ).dict()
    )

@router.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    logger.error(f\"Unhandled exception: {str(exc)}\", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content=ErrorResponse(
            error=ErrorDetail(
                code=\"INTERNAL_ERROR\",
                message=\"An internal error occurred\",
                details={\"request_path\": str(request.url.path)}
            )
        ).dict()
    )
```

## ✅ 完了条件
- [ ] メインAPIエンドポイントの実装
- [ ] ヘルスチェックエンドポイント
- [ ] 統計情報エンドポイント
- [ ] エラーハンドリング
- [ ] ログ機能
- [ ] 依存性注入の設定
- [ ] 統合テスト

## 🧪 テスト内容
```python
import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, patch

async def test_co2_status_endpoint():
    \"\"\"CO2ステータスエンドポイントのテスト\"\"\"
    
    # モックの準備
    mock_accessor = AsyncMock()
    mock_engine = AsyncMock()
    
    # レスポンス設定
    mock_latest = {
        'co2': 950,
        'temperature': 23.5,
        'datetime': datetime.now()
    }
    mock_accessor.get_latest_reading.return_value = mock_latest
    
    # APIテスト
    with TestClient(app) as client:
        response = client.get(\"/api/air-quality/co2-status?hours=3\")
        
        assert response.status_code == 200
        data = response.json()
        
        assert \"status\" in data
        assert \"current\" in data
        assert \"analysis\" in data
        assert \"message\" in data
        assert \"recommendations\" in data

async def test_invalid_hours_parameter():
    \"\"\"無効な時間パラメータのテスト\"\"\"
    
    with TestClient(app) as client:
        # 範囲外の値
        response = client.get(\"/api/air-quality/co2-status?hours=0\")
        assert response.status_code == 422  # Validation Error
        
        response = client.get(\"/api/air-quality/co2-status?hours=200\")
        assert response.status_code == 422

async def test_health_endpoint():
    \"\"\"ヘルスチェックエンドポイントのテスト\"\"\"
    
    with TestClient(app) as client:
        response = client.get(\"/api/air-quality/health\")
        
        assert response.status_code == 200
        data = response.json()
        
        assert \"status\" in data
        assert \"database_status\" in data
        assert \"version\" in data
        assert \"uptime_seconds\" in data

async def test_database_error_handling():
    \"\"\"データベースエラーのハンドリングテスト\"\"\"
    
    with patch('database.air_quality_accessor.AirQualityDatabaseAccessor') as mock_accessor:
        mock_accessor.return_value.get_latest_reading.side_effect = Exception(\"DB Error\")
        
        with TestClient(app) as client:
            response = client.get(\"/api/air-quality/co2-status\")
            
            assert response.status_code == 500
            assert \"error\" in response.json()
```

## 📁 ファイル構成
```
src/openapi_server/
├── apis/
│   ├── air_quality_api.py      # 新規作成
│   └── __init__.py
├── impl/
│   ├── air_quality_api_impl.py # 新規作成
│   └── __init__.py
└── main.py                     # 更新（ルーター追加）
tests/
└── test_air_quality_api.py     # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #7 Pydanticモデル定義
- 次のIssue: #9 エラーハンドリングと入力検証

## 🎯 統合のポイント
- **依存性注入**: FastAPIのDependsを活用したクリーンな設計
- **エラーハンドリング**: 適切なHTTPステータスコードとメッセージ
- **ログ**: デバッグとモニタリングのための詳細ログ
- **パフォーマンス**: 非同期処理による高いスループット