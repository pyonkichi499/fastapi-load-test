# Issue #7: Pydanticモデル定義

## 📋 概要
CO2モニタリングAPIのリクエスト・レスポンス用Pydanticモデルを定義し、型安全性とバリデーションを確保する

## 🎯 目標
- 型安全なAPIインターフェース
- 入力値のバリデーション
- JSON Schemaの自動生成
- OpenAPI仕様の自動生成

## 📝 詳細要件

### レスポンスモデル

#### 1. メインレスポンス
```python
from pydantic import BaseModel, Field, validator
from datetime import datetime
from typing import List, Optional, Literal

class CurrentReading(BaseModel):
    \"\"\"現在の測定値\"\"\"
    co2: int = Field(..., description=\"CO2濃度 (ppm)\", ge=0, le=5000)
    temperature: float = Field(..., description=\"温度 (℃)\", ge=-50, le=100)
    timestamp: datetime = Field(..., description=\"測定時刻\")

class AnalysisData(BaseModel):
    \"\"\"分析結果データ\"\"\"
    period_hours: int = Field(..., description=\"分析期間 (時間)\", ge=1, le=168)
    avg_co2: float = Field(..., description=\"平均CO2濃度\", ge=0)
    max_co2: int = Field(..., description=\"最大CO2濃度\", ge=0)
    min_co2: int = Field(..., description=\"最小CO2濃度\", ge=0)
    
    trend: Literal[\"急上昇\", \"上昇傾向\", \"安定\", \"下降傾向\", \"急下降\"] = Field(
        ..., description=\"トレンド\"
    )
    
    high_co2_duration_minutes: int = Field(
        ..., description=\"高CO2状態継続時間 (分)\", ge=0
    )
    
    data_points: int = Field(..., description=\"データポイント数\", ge=0)
    
    # 予測データ（オプション）
    predicted_co2_30min: Optional[float] = Field(
        None, description=\"30分後の予測CO2濃度\", ge=0
    )
    
    trend_confidence: Optional[float] = Field(
        None, description=\"トレンド予測の信頼度 (0-1)\", ge=0, le=1
    )

class TimelinePoint(BaseModel):
    \"\"\"時系列データポイント\"\"\"
    timestamp: datetime = Field(..., description=\"測定時刻\")
    co2: int = Field(..., description=\"CO2濃度 (ppm)\", ge=0)
    temperature: float = Field(..., description=\"温度 (℃)\")
    
    # 分析用追加データ
    moving_avg_10min: Optional[float] = Field(
        None, description=\"10分移動平均\", ge=0
    )
    
    change_from_previous: Optional[int] = Field(
        None, description=\"前回からの変化量 (ppm)\"
    )

class AirQualityResponse(BaseModel):
    \"\"\"メインレスポンス\"\"\"
    
    # 基本ステータス
    status: Literal[\"良好\", \"注意\", \"危険\"] = Field(
        ..., description=\"空気質ステータス\"
    )
    
    # 現在の測定値
    current: CurrentReading = Field(..., description=\"現在の測定値\")
    
    # 分析結果
    analysis: AnalysisData = Field(..., description=\"分析結果\")
    
    # メッセージとアクション
    message: str = Field(..., description=\"状況説明メッセージ\", min_length=1)
    
    action: Literal[\"問題なし\", \"換気推奨\", \"即座に換気\"] = Field(
        ..., description=\"推奨アクション\"
    )
    
    recommendations: List[str] = Field(
        ..., description=\"具体的な推奨事項\", min_items=1
    )
    
    # 時系列データ（オプション）
    timeline: Optional[List[TimelinePoint]] = Field(
        None, description=\"時系列データ\"
    )
    
    # メタデータ
    generated_at: datetime = Field(
        default_factory=datetime.now, description=\"レスポンス生成時刻\"
    )
    
    @validator('timeline')
    def validate_timeline(cls, v, values):
        \"\"\"時系列データのバリデーション\"\"\"
        if v is not None and len(v) > 1000:
            raise ValueError('Timeline data too large (max 1000 points)')
        return v
    
    @validator('recommendations')
    def validate_recommendations(cls, v):
        \"\"\"推奨事項のバリデーション\"\"\"
        if len(v) > 10:
            raise ValueError('Too many recommendations (max 10)')
        return v
```

#### 2. エラーレスポンス
```python
class ErrorDetail(BaseModel):
    \"\"\"エラー詳細\"\"\"
    code: str = Field(..., description=\"エラーコード\")
    message: str = Field(..., description=\"エラーメッセージ\")
    details: Optional[dict] = Field(None, description=\"詳細情報\")

class ErrorResponse(BaseModel):
    \"\"\"エラーレスポンス\"\"\"
    error: ErrorDetail = Field(..., description=\"エラー情報\")
    timestamp: datetime = Field(
        default_factory=datetime.now, description=\"エラー発生時刻\"
    )
    request_id: Optional[str] = Field(None, description=\"リクエストID\")
```

### リクエストモデル

#### 1. クエリパラメータ
```python
from pydantic import BaseModel, Field

class AirQualityQueryParams(BaseModel):
    \"\"\"クエリパラメータ\"\"\"
    
    hours: int = Field(
        default=3, 
        description=\"分析期間（時間）\",
        ge=1, 
        le=168,  # 最大1週間
        example=3
    )
    
    include_timeline: bool = Field(
        default=True,
        description=\"時系列データを含めるか\"
    )
    
    timeline_resolution: Literal[\"1min\", \"5min\", \"10min\", \"30min\"] = Field(
        default=\"5min\",
        description=\"時系列データの解像度\"
    )
    
    include_predictions: bool = Field(
        default=False,
        description=\"予測データを含めるか\"
    )
    
    @validator('hours')
    def validate_hours(cls, v):
        \"\"\"時間数のバリデーション\"\"\"
        if v > 24 and v % 24 != 0:
            raise ValueError('Hours > 24 must be multiple of 24')
        return v
```

### 設定モデル

#### 1. CO2閾値設定
```python
class CO2Thresholds(BaseModel):
    \"\"\"CO2濃度閾値設定\"\"\"
    
    good_max: int = Field(
        default=800, 
        description=\"良好レベルの上限 (ppm)\",
        ge=400, 
        le=1000
    )
    
    caution_max: int = Field(
        default=1200,
        description=\"注意レベルの上限 (ppm)\",
        ge=800,
        le=2000
    )
    
    # danger_level は caution_max 超過
    
    @validator('caution_max')
    def validate_caution_max(cls, v, values):
        \"\"\"注意レベル上限のバリデーション\"\"\"
        if 'good_max' in values and v <= values['good_max']:
            raise ValueError('caution_max must be greater than good_max')
        return v

class AnalysisSettings(BaseModel):
    \"\"\"分析設定\"\"\"
    
    thresholds: CO2Thresholds = Field(
        default_factory=CO2Thresholds,
        description=\"CO2濃度閾値\"
    )
    
    trend_analysis_window: int = Field(
        default=60,
        description=\"トレンド分析の窓サイズ（分）\",
        ge=30,
        le=180
    )
    
    high_co2_alert_duration: int = Field(
        default=30,
        description=\"高CO2アラートまでの継続時間（分）\",
        ge=10,
        le=120
    )
```

### ヘルスチェック用モデル

#### 1. システム状態
```python
class SystemHealth(BaseModel):
    \"\"\"システムヘルス\"\"\"
    
    status: Literal[\"healthy\", \"degraded\", \"unhealthy\"] = Field(
        ..., description=\"システム状態\"
    )
    
    database_status: Literal[\"connected\", \"disconnected\", \"error\"] = Field(
        ..., description=\"データベース接続状態\"
    )
    
    last_data_timestamp: Optional[datetime] = Field(
        None, description=\"最新データの時刻\"
    )
    
    data_freshness_minutes: Optional[int] = Field(
        None, description=\"データの新しさ（分）\"
    )
    
    version: str = Field(..., description=\"APIバージョン\")
    
    uptime_seconds: int = Field(..., description=\"稼働時間（秒）\", ge=0)
```

## ✅ 完了条件
- [ ] 全レスポンスモデルの実装
- [ ] バリデーションロジックの実装
- [ ] カスタムバリデータの実装
- [ ] エラーハンドリングモデル
- [ ] JSON Schemaの確認
- [ ] ドキュメント例の作成

## 🧪 テスト内容
```python
def test_air_quality_response_validation():
    \"\"\"メインレスポンスのバリデーションテスト\"\"\"
    
    # 正常データ
    valid_data = {
        \"status\": \"注意\",
        \"current\": {
            \"co2\": 950,
            \"temperature\": 23.5,
            \"timestamp\": datetime.now()
        },
        \"analysis\": {
            \"period_hours\": 3,
            \"avg_co2\": 780.5,
            \"max_co2\": 1200,
            \"min_co2\": 450,
            \"trend\": \"上昇傾向\",
            \"high_co2_duration_minutes\": 45,
            \"data_points\": 180
        },
        \"message\": \"CO2濃度が上昇傾向です\",
        \"action\": \"換気推奨\",
        \"recommendations\": [\"窓を開けてください\"]
    }
    
    response = AirQualityResponse(**valid_data)
    assert response.status == \"注意\"
    assert response.current.co2 == 950

def test_invalid_co2_value():
    \"\"\"無効なCO2値のテスト\"\"\"
    
    with pytest.raises(ValidationError):
        CurrentReading(
            co2=-100,  # 負の値は無効
            temperature=23.5,
            timestamp=datetime.now()
        )
    
    with pytest.raises(ValidationError):
        CurrentReading(
            co2=10000,  # 範囲外
            temperature=23.5,
            timestamp=datetime.now()
        )

def test_query_params_validation():
    \"\"\"クエリパラメータのバリデーションテスト\"\"\"
    
    # 正常値
    params = AirQualityQueryParams(hours=6, include_timeline=True)
    assert params.hours == 6
    
    # 範囲外
    with pytest.raises(ValidationError):
        AirQualityQueryParams(hours=0)  # 最小値未満
    
    with pytest.raises(ValidationError):
        AirQualityQueryParams(hours=200)  # 最大値超過

def test_timeline_size_limit():
    \"\"\"時系列データサイズ制限のテスト\"\"\"
    
    large_timeline = [
        TimelinePoint(
            timestamp=datetime.now(),
            co2=800,
            temperature=23.0
        ) for _ in range(1001)  # 制限超過
    ]
    
    with pytest.raises(ValidationError):
        AirQualityResponse(
            status=\"良好\",
            current=CurrentReading(co2=800, temperature=23.0, timestamp=datetime.now()),
            analysis=AnalysisData(
                period_hours=3,
                avg_co2=800,
                max_co2=850,
                min_co2=750,
                trend=\"安定\",
                high_co2_duration_minutes=0,
                data_points=180
            ),
            message=\"テスト\",
            action=\"問題なし\",
            recommendations=[\"維持してください\"],
            timeline=large_timeline
        )

def test_co2_thresholds_validation():
    \"\"\"CO2閾値のバリデーションテスト\"\"\"
    
    # 正常値
    thresholds = CO2Thresholds(good_max=800, caution_max=1200)
    assert thresholds.good_max < thresholds.caution_max
    
    # 無効な組み合わせ
    with pytest.raises(ValidationError):
        CO2Thresholds(good_max=1000, caution_max=800)  # 逆転
```

## 📁 ファイル構成
```
src/openapi_server/models/
├── __init__.py
├── air_quality.py          # 新規作成
├── request_models.py       # 新規作成
├── response_models.py      # 新規作成
├── error_models.py         # 新規作成
└── config_models.py        # 新規作成
tests/
└── test_pydantic_models.py # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #6 CO2分析ロジック実装
- 次のIssue: #8 CO2ステータスAPI実装

## 🎯 設計原則
- **厳密なバリデーション**: 不正データの早期検出
- **わかりやすいエラー**: 具体的なバリデーションエラーメッセージ
- **拡張性**: 将来の機能追加に対応
- **ドキュメント化**: 自動生成されるAPIドキュメントの品質向上

## 📚 Pydantic機能活用
- **Field**: 詳細なバリデーションルール
- **validator**: カスタムバリデーションロジック
- **Literal**: 限定された値の選択肢
- **default_factory**: 動的デフォルト値