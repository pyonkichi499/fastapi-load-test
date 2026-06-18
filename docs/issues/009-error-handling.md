# Issue #9: エラーハンドリングと入力検証

## 📋 概要
堅牢なエラーハンドリングシステムと包括的な入力検証を実装し、APIの信頼性を向上させる

## 🎯 目標
- 包括的なエラーハンドリング
- ユーザーフレンドリーなエラーメッセージ
- セキュリティを考慮した情報開示
- ログとモニタリングの統合

## 📝 詳細要件

### カスタム例外クラス

#### 1. 基底例外クラス
```python
class AirQualityException(Exception):
    \"\"\"空気質API用基底例外クラス\"\"\"
    
    def __init__(
        self, 
        message: str, 
        error_code: str = None,
        details: dict = None,
        status_code: int = 500
    ):
        self.message = message
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}
        self.status_code = status_code
        super().__init__(self.message)

class DataNotFoundError(AirQualityException):
    \"\"\"データが見つからない場合の例外\"\"\"
    
    def __init__(self, message: str = \"No data found\", **kwargs):
        super().__init__(message, status_code=404, **kwargs)

class DatabaseConnectionError(AirQualityException):
    \"\"\"データベース接続エラー\"\"\"
    
    def __init__(self, message: str = \"Database connection failed\", **kwargs):
        super().__init__(message, status_code=503, **kwargs)

class ValidationError(AirQualityException):
    \"\"\"バリデーションエラー\"\"\"
    
    def __init__(self, message: str = \"Validation failed\", **kwargs):
        super().__init__(message, status_code=400, **kwargs)

class RateLimitError(AirQualityException):
    \"\"\"レート制限エラー\"\"\"
    
    def __init__(self, message: str = \"Rate limit exceeded\", **kwargs):
        super().__init__(message, status_code=429, **kwargs)

class ConfigurationError(AirQualityException):
    \"\"\"設定エラー\"\"\"
    
    def __init__(self, message: str = \"Configuration error\", **kwargs):
        super().__init__(message, status_code=500, **kwargs)
```

#### 2. ビジネスロジック例外
```python
class InsufficientDataError(AirQualityException):
    \"\"\"分析に必要なデータが不足\"\"\"
    
    def __init__(self, required_hours: int, available_hours: float, **kwargs):
        message = f\"Insufficient data: required {required_hours}h, available {available_hours:.1f}h\"
        details = {
            \"required_hours\": required_hours,
            \"available_hours\": available_hours
        }
        super().__init__(message, status_code=422, details=details, **kwargs)

class SensorMalfunctionError(AirQualityException):
    \"\"\"センサー異常検知\"\"\"
    
    def __init__(self, sensor_issue: str, **kwargs):
        message = f\"Sensor malfunction detected: {sensor_issue}\"
        details = {\"sensor_issue\": sensor_issue}
        super().__init__(message, status_code=503, details=details, **kwargs)

class DataQualityError(AirQualityException):
    \"\"\"データ品質問題\"\"\"
    
    def __init__(self, quality_issue: str, **kwargs):
        message = f\"Data quality issue: {quality_issue}\"
        details = {\"quality_issue\": quality_issue}
        super().__init__(message, status_code=422, details=details, **kwargs)
```

### エラーハンドラー実装

#### 1. グローバル例外ハンドラー
```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
import logging
import traceback
import uuid
from datetime import datetime

logger = logging.getLogger(__name__)

def setup_error_handlers(app: FastAPI):
    \"\"\"エラーハンドラーの設定\"\"\"
    
    @app.exception_handler(AirQualityException)
    async def air_quality_exception_handler(request: Request, exc: AirQualityException):
        \"\"\"カスタム例外ハンドラー\"\"\"
        
        request_id = str(uuid.uuid4())
        
        logger.error(
            f\"AirQualityException: {exc.message}\",
            extra={
                \"request_id\": request_id,
                \"error_code\": exc.error_code,
                \"status_code\": exc.status_code,
                \"path\": str(request.url.path),
                \"method\": request.method,
                \"details\": exc.details
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=exc.error_code,
                    message=exc.message,
                    details=exc.details
                ),
                request_id=request_id
            ).dict()
        )
    
    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        \"\"\"Pydanticバリデーションエラーハンドラー\"\"\"
        
        request_id = str(uuid.uuid4())
        
        # バリデーションエラーの詳細を整理
        error_details = []
        for error in exc.errors():
            error_details.append({
                \"field\": \".\".join(str(x) for x in error[\"loc\"]),
                \"message\": error[\"msg\"],
                \"type\": error[\"type\"],
                \"input\": error.get(\"input\")
            })
        
        logger.warning(
            f\"Validation error: {len(error_details)} validation errors\",
            extra={
                \"request_id\": request_id,
                \"path\": str(request.url.path),
                \"errors\": error_details
            }
        )
        
        return JSONResponse(
            status_code=422,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=\"VALIDATION_ERROR\",
                    message=\"Request validation failed\",
                    details={
                        \"validation_errors\": error_details
                    }
                ),
                request_id=request_id
            ).dict()
        )
    
    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        \"\"\"FastAPI HTTPExceptionハンドラー\"\"\"
        
        request_id = str(uuid.uuid4())
        
        logger.warning(
            f\"HTTP {exc.status_code}: {exc.detail}\",
            extra={
                \"request_id\": request_id,
                \"status_code\": exc.status_code,
                \"path\": str(request.url.path)
            }
        )
        
        return JSONResponse(
            status_code=exc.status_code,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=f\"HTTP_{exc.status_code}\",
                    message=exc.detail,
                    details={}
                ),
                request_id=request_id
            ).dict()
        )
    
    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        \"\"\"未処理例外ハンドラー\"\"\"
        
        request_id = str(uuid.uuid4())
        
        logger.error(
            f\"Unhandled exception: {str(exc)}\",
            extra={
                \"request_id\": request_id,
                \"path\": str(request.url.path),
                \"method\": request.method,
                \"exception_type\": type(exc).__name__,
                \"traceback\": traceback.format_exc()
            }
        )
        
        # 本番環境では詳細なエラー情報を隠す
        is_development = os.getenv(\"ENVIRONMENT\", \"production\") == \"development\"
        
        if is_development:
            message = f\"Internal error: {str(exc)}\"
            details = {\"traceback\": traceback.format_exc()}
        else:
            message = \"An internal error occurred\"
            details = {}
        
        return JSONResponse(
            status_code=500,
            content=ErrorResponse(
                error=ErrorDetail(
                    code=\"INTERNAL_ERROR\",
                    message=message,
                    details=details
                ),
                request_id=request_id
            ).dict()
        )
```

### 入力検証強化

#### 1. カスタムバリデーター
```python
from pydantic import validator, Field
from datetime import datetime, timedelta

class EnhancedAirQualityQueryParams(BaseModel):
    \"\"\"強化された入力検証\"\"\"
    
    hours: int = Field(
        default=3,
        description=\"分析期間（時間）\",
        ge=1,
        le=168,
        example=3
    )
    
    include_timeline: bool = Field(
        default=True,
        description=\"時系列データを含めるか\"
    )
    
    timeline_resolution: str = Field(
        default=\"5min\",
        description=\"時系列データの解像度\"
    )
    
    max_data_points: int = Field(
        default=500,
        description=\"最大データポイント数\",
        ge=10,
        le=2000
    )
    
    @validator('hours')
    def validate_hours(cls, v):
        \"\"\"時間数の高度なバリデーション\"\"\"
        
        # 24時間を超える場合は24の倍数
        if v > 24 and v % 24 != 0:
            raise ValueError(\"Hours > 24 must be multiple of 24\")
        
        # 週末を跨ぐ長期間はデータ不足の可能性
        if v > 72:
            raise ValueError(\"Analysis period too long (max 72 hours)\")
        
        return v
    
    @validator('timeline_resolution')
    def validate_resolution(cls, v):
        \"\"\"解像度の検証\"\"\"
        
        valid_resolutions = [\"1min\", \"5min\", \"10min\", \"30min\", \"1hour\"]
        if v not in valid_resolutions:
            raise ValueError(f\"Invalid resolution. Must be one of: {valid_resolutions}\")
        
        return v
    
    @validator('max_data_points')
    def validate_max_data_points(cls, v, values):
        \"\"\"データポイント数の妥当性検証\"\"\"
        
        if 'hours' in values:
            hours = values['hours']
            # 1分間隔で最大データポイント数を超えないか確認
            max_theoretical_points = hours * 60
            
            if v > max_theoretical_points:
                raise ValueError(
                    f\"max_data_points ({v}) cannot exceed theoretical maximum ({max_theoretical_points}) for {hours} hours\"
                )
        
        return v
```

#### 2. データ品質検証
```python
class DataQualityValidator:
    \"\"\"データ品質検証クラス\"\"\"
    
    @staticmethod
    def validate_co2_reading(co2_value: int, timestamp: datetime) -> None:
        \"\"\"CO2測定値の妥当性検証\"\"\"
        
        # 物理的に不可能な値
        if co2_value < 250 or co2_value > 5000:
            raise SensorMalfunctionError(
                f\"CO2 value out of physical range: {co2_value}ppm\"
            )
        
        # 急激な変化の検知（前回値と比較）
        # この部分は実装時に前回値を取得して比較
        
        # 未来の時刻
        if timestamp > datetime.now() + timedelta(minutes=5):
            raise DataQualityError(
                f\"Future timestamp detected: {timestamp}\"
            )
        
        # 古すぎるデータ
        if timestamp < datetime.now() - timedelta(days=30):
            raise DataQualityError(
                f\"Data too old: {timestamp}\"
            )
    
    @staticmethod
    def validate_temperature_reading(temp_value: float, timestamp: datetime) -> None:
        \"\"\"温度測定値の妥当性検証\"\"\"
        
        # 室温として異常な値
        if temp_value < -10 or temp_value > 50:
            raise SensorMalfunctionError(
                f\"Temperature out of reasonable range: {temp_value}°C\"
            )
    
    @staticmethod
    def validate_data_continuity(readings: List[Dict]) -> None:
        \"\"\"データの連続性検証\"\"\"
        
        if len(readings) < 2:
            return
        
        # 時系列順でない場合
        for i in range(1, len(readings)):
            if readings[i]['datetime'] <= readings[i-1]['datetime']:
                raise DataQualityError(\"Data not in chronological order\")
        
        # 大きな時間間隔の検出
        gaps = []
        for i in range(1, len(readings)):
            gap = (readings[i]['datetime'] - readings[i-1]['datetime']).total_seconds() / 60
            if gap > 10:  # 10分以上の間隔
                gaps.append(gap)
        
        if gaps and max(gaps) > 60:  # 1時間以上の欠落
            raise InsufficientDataError(
                required_hours=0,
                available_hours=0,
                details={\"max_gap_minutes\": max(gaps)}
            )
```

### ログとモニタリング

#### 1. 構造化ログ
```python
import structlog
import json

def setup_logging():
    \"\"\"構造化ログの設定\"\"\"
    
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt=\"iso\"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer()
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

class AirQualityLogger:
    \"\"\"空気質API専用ログ\"\"\"
    
    def __init__(self):
        self.logger = structlog.get_logger()
    
    def log_api_request(self, request: Request, params: dict):
        \"\"\"APIリクエストログ\"\"\"
        self.logger.info(
            \"api_request\",
            path=str(request.url.path),
            method=request.method,
            params=params,
            user_agent=request.headers.get(\"user-agent\"),
            client_ip=request.client.host
        )
    
    def log_analysis_result(self, result: AirQualityResponse, duration_ms: float):
        \"\"\"分析結果ログ\"\"\"
        self.logger.info(
            \"analysis_completed\",
            status=result.status,
            co2_level=result.current.co2,
            action=result.action,
            duration_ms=duration_ms,
            data_points=result.analysis.data_points
        )
    
    def log_data_quality_issue(self, issue: str, details: dict):
        \"\"\"データ品質問題ログ\"\"\"
        self.logger.warning(
            \"data_quality_issue\",
            issue=issue,
            details=details
        )
```

## ✅ 完了条件
- [ ] カスタム例外クラスの実装
- [ ] グローバル例外ハンドラーの設定
- [ ] 強化された入力検証
- [ ] データ品質検証システム
- [ ] 構造化ログの実装
- [ ] エラーレスポンスの統一
- [ ] セキュリティ考慮事項の実装

## 🧪 テスト内容
```python
async def test_custom_exception_handling():
    \"\"\"カスタム例外ハンドリングのテスト\"\"\"
    
    with pytest.raises(DataNotFoundError) as exc_info:
        raise DataNotFoundError(\"Test data not found\")
    
    assert exc_info.value.status_code == 404
    assert \"Test data not found\" in str(exc_info.value)

async def test_validation_error_response():
    \"\"\"バリデーションエラーレスポンスのテスト\"\"\"
    
    with TestClient(app) as client:
        response = client.get(\"/api/air-quality/co2-status?hours=-1\")
        
        assert response.status_code == 422
        error_data = response.json()
        
        assert \"error\" in error_data
        assert error_data[\"error\"][\"code\"] == \"VALIDATION_ERROR\"
        assert \"validation_errors\" in error_data[\"error\"][\"details\"]

async def test_data_quality_validation():
    \"\"\"データ品質検証のテスト\"\"\"
    
    # 異常なCO2値
    with pytest.raises(SensorMalfunctionError):
        DataQualityValidator.validate_co2_reading(-100, datetime.now())
    
    with pytest.raises(SensorMalfunctionError):
        DataQualityValidator.validate_co2_reading(10000, datetime.now())
    
    # 未来の時刻
    with pytest.raises(DataQualityError):
        future_time = datetime.now() + timedelta(hours=1)
        DataQualityValidator.validate_co2_reading(800, future_time)

async def test_error_logging():
    \"\"\"エラーログのテスト\"\"\"
    
    logger = AirQualityLogger()
    
    with patch('structlog.get_logger') as mock_logger:
        logger.log_data_quality_issue(
            \"Abnormal CO2 spike\",
            {\"co2_value\": 3000, \"previous_value\": 800}
        )
        
        mock_logger.return_value.warning.assert_called_once()

async def test_insufficient_data_handling():
    \"\"\"データ不足ハンドリングのテスト\"\"\"
    
    with pytest.raises(InsufficientDataError) as exc_info:
        raise InsufficientDataError(required_hours=3, available_hours=1.5)
    
    error = exc_info.value
    assert error.status_code == 422
    assert error.details[\"required_hours\"] == 3
    assert error.details[\"available_hours\"] == 1.5
```

## 📁 ファイル構成
```
src/
├── exceptions/
│   ├── __init__.py
│   ├── air_quality_exceptions.py  # 新規作成
│   └── error_handlers.py         # 新規作成
├── validation/
│   ├── __init__.py
│   ├── data_quality.py           # 新規作成
│   └── input_validators.py       # 新規作成
├── logging/
│   ├── __init__.py
│   └── structured_logging.py     # 新規作成
tests/
├── test_error_handling.py        # 新規作成
├── test_data_validation.py       # 新規作成
└── test_logging.py               # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #8 CO2ステータスAPI実装
- 次のIssue: #10 単体テスト実装

## 🛡️ セキュリティ考慮事項
- **情報開示**: 本番環境では内部エラー詳細を隠蔽
- **ログ**: 機密情報をログに記録しない
- **バリデーション**: SQLインジェクション対策
- **レート制限**: API乱用防止