# Issue #10: 単体テスト実装

## 📋 概要
CO2モニタリングAPIの全コンポーネントに対する包括的な単体テストを実装し、コードの品質と信頼性を確保する

## 🎯 目標
- 高いテストカバレッジ（90%以上）
- 堅牢なモックとフィクスチャ
- 継続的インテグレーション対応
- パフォーマンステスト

## 📝 詳細要件

### テスト構成

#### 1. テストディレクトリ構造
```
tests/
├── __init__.py
├── conftest.py                    # pytest設定とフィクスチャ
├── unit/
│   ├── __init__.py
│   ├── test_bigquery_client.py    # BigQueryクライアント
│   ├── test_air_quality_accessor.py # データアクセサー
│   ├── test_co2_analysis_engine.py # 分析エンジン
│   ├── test_pydantic_models.py    # モデル検証
│   └── test_error_handling.py     # エラーハンドリング
├── integration/
│   ├── __init__.py
│   ├── test_api_endpoints.py      # APIエンドポイント
│   └── test_database_integration.py # DB統合テスト
├── performance/
│   ├── __init__.py
│   └── test_performance.py        # パフォーマンステスト
└── fixtures/
    ├── __init__.py
    ├── sample_data.py             # テストデータ
    └── mock_responses.py          # モックレスポンス
```

### フィクスチャ定義

#### 1. pytest設定（conftest.py）
```python
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock
from typing import List, Dict

from database.air_quality_config import AirQualitySettings
from database.air_quality_accessor import AirQualityDatabaseAccessor
from analysis.co2_analysis_engine import CO2AnalysisEngine

@pytest.fixture
def mock_settings():
    \"\"\"モック設定\"\"\"
    settings = MagicMock(spec=AirQualitySettings)
    settings.PROJECT_ID = \"test-project\"
    settings.BIGQUERY_DATASET = \"test_dataset\"
    settings.BIGQUERY_TABLE = \"test_table\"
    settings.USE_BIGQUERY = False
    settings.SQLITE_PATH = \":memory:\"
    return settings

@pytest.fixture
def sample_co2_readings():
    \"\"\"サンプルCO2データ\"\"\"
    base_time = datetime.now() - timedelta(hours=3)
    readings = []
    
    for i in range(180):  # 3時間分（1分間隔）
        timestamp = base_time + timedelta(minutes=i)
        
        # 時間帯によるCO2パターン
        if i < 60:  # 最初の1時間：低濃度
            co2 = 450 + (i * 2) + (i % 10) * 5
        elif i < 120:  # 2時間目：急上昇
            co2 = 570 + ((i - 60) * 8) + (i % 15) * 10
        else:  # 3時間目：高濃度維持
            co2 = 1050 + (i % 20) * 5
        
        temperature = 22.0 + (i * 0.01) + (i % 30) * 0.1
        
        readings.append({
            'datetime': timestamp,
            'co2': int(co2),
            'temperature': round(temperature, 1),
            'data': None
        })
    
    return readings

@pytest.fixture
def mock_db_accessor(sample_co2_readings):
    \"\"\"モックデータベースアクセサー\"\"\"
    accessor = AsyncMock(spec=AirQualityDatabaseAccessor)
    
    # 最新読み取り値
    accessor.get_latest_reading.return_value = sample_co2_readings[-1]
    
    # 期間別データ
    def get_readings_by_hours(hours: int):
        cutoff_time = datetime.now() - timedelta(hours=hours)
        return [r for r in sample_co2_readings if r['datetime'] >= cutoff_time]
    
    accessor.get_readings_by_hours.side_effect = get_readings_by_hours
    
    # 統計データ
    accessor.get_co2_statistics.return_value = {
        'avg_co2': 750.5,
        'max_co2': 1200,
        'min_co2': 450,
        'data_points': len(sample_co2_readings)
    }
    
    return accessor

@pytest.fixture
def analysis_engine():
    \"\"\"分析エンジンインスタンス\"\"\"
    return CO2AnalysisEngine()

@pytest_asyncio.fixture
async def test_app():
    \"\"\"テスト用FastAPIアプリ\"\"\"
    from openapi_server.main import app
    return app
```

#### 2. テストデータ生成（fixtures/sample_data.py）
```python
from datetime import datetime, timedelta
from typing import List, Dict
import random
import math

class TestDataGenerator:
    \"\"\"テストデータ生成クラス\"\"\"
    
    @staticmethod
    def generate_co2_pattern(
        hours: int = 24,
        interval_minutes: int = 1,
        base_co2: int = 450,
        pattern_type: str = \"normal\"
    ) -> List[Dict]:
        \"\"\"様々なパターンのCO2データを生成\"\"\"
        
        data = []
        start_time = datetime.now() - timedelta(hours=hours)
        total_points = hours * 60 // interval_minutes
        
        for i in range(total_points):
            timestamp = start_time + timedelta(minutes=i * interval_minutes)
            
            if pattern_type == \"normal\":
                co2 = TestDataGenerator._normal_pattern(i, total_points, base_co2)
            elif pattern_type == \"spike\":
                co2 = TestDataGenerator._spike_pattern(i, total_points, base_co2)
            elif pattern_type == \"ventilation\":
                co2 = TestDataGenerator._ventilation_pattern(i, total_points, base_co2)
            elif pattern_type == \"gradual_increase\":
                co2 = TestDataGenerator._gradual_increase_pattern(i, total_points, base_co2)
            else:
                co2 = base_co2
            
            temperature = 22.0 + random.uniform(-2.0, 2.0)
            
            data.append({
                'datetime': timestamp,
                'co2': max(400, min(2000, int(co2))),
                'temperature': round(temperature, 1),
                'data': None
            })
        
        return data
    
    @staticmethod
    def _normal_pattern(i: int, total: int, base: int) -> int:
        \"\"\"正常な日内変動パターン\"\"\"
        # 時間帯による変動（24時間周期）
        hour_cycle = 2 * math.pi * i / (total / 24)
        daily_variation = 100 * math.sin(hour_cycle)
        
        # ランダムノイズ
        noise = random.uniform(-30, 30)
        
        return base + daily_variation + noise
    
    @staticmethod
    def _spike_pattern(i: int, total: int, base: int) -> int:
        \"\"\"スパイク（急上昇）パターン\"\"\"
        # 中間地点でスパイク
        spike_center = total // 2
        spike_width = total // 10
        
        if abs(i - spike_center) < spike_width:
            spike_height = 600 * (1 - abs(i - spike_center) / spike_width)
            return base + spike_height
        
        return base + random.uniform(-20, 20)
    
    @staticmethod
    def _ventilation_pattern(i: int, total: int, base: int) -> int:
        \"\"\"換気効果パターン\"\"\"
        # 前半は上昇、中間で換気（急下降）、後半は緩やかな上昇
        ventilation_point = total // 3
        
        if i < ventilation_point:
            # 上昇フェーズ
            return base + (i / ventilation_point) * 400
        elif i < ventilation_point * 1.5:
            # 換気フェーズ（急下降）
            drop_ratio = (i - ventilation_point) / (ventilation_point * 0.5)
            return base + 400 - (drop_ratio * 350)
        else:
            # 回復フェーズ
            recovery_ratio = (i - ventilation_point * 1.5) / (total - ventilation_point * 1.5)
            return base + 50 + (recovery_ratio * 200)
    
    @staticmethod
    def _gradual_increase_pattern(i: int, total: int, base: int) -> int:
        \"\"\"緩やかな上昇パターン\"\"\"
        return base + (i / total) * 500 + random.uniform(-15, 15)

class MockResponseGenerator:
    \"\"\"モックレスポンス生成\"\"\"
    
    @staticmethod
    def bigquery_response(data: List[Dict]) -> List[Dict]:
        \"\"\"BigQueryレスポンス形式\"\"\"
        return [
            {
                'datetime': row['datetime'].isoformat(),
                'co2': row['co2'],
                'temperature': row['temperature'],
                'data': row['data']
            }
            for row in data
        ]
    
    @staticmethod
    def error_response(error_code: str, message: str) -> Dict:
        \"\"\"エラーレスポンス\"\"\"
        return {
            'error': {
                'code': error_code,
                'message': message,
                'details': {}
            },
            'timestamp': datetime.now().isoformat(),
            'request_id': 'test-request-id'
        }
```

### 単体テスト実装

#### 1. データベースアクセサーテスト
```python
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch
from datetime import datetime, timedelta

from database.air_quality_accessor import AirQualityDatabaseAccessor
from exceptions.air_quality_exceptions import DataNotFoundError, DatabaseConnectionError

class TestAirQualityDatabaseAccessor:
    \"\"\"AirQualityDatabaseAccessorのテスト\"\"\"
    
    @pytest_asyncio.async_test
    async def test_get_latest_reading_success(self, mock_db_accessor, sample_co2_readings):
        \"\"\"最新データ取得の成功テスト\"\"\"
        
        result = await mock_db_accessor.get_latest_reading()
        
        assert result is not None
        assert 'datetime' in result
        assert 'co2' in result
        assert 'temperature' in result
        assert isinstance(result['co2'], int)
        assert isinstance(result['temperature'], float)
    
    @pytest_asyncio.async_test
    async def test_get_latest_reading_no_data(self, mock_settings):
        \"\"\"データなしの場合のテスト\"\"\"
        
        accessor = AirQualityDatabaseAccessor(mock_settings)
        
        with patch.object(accessor, 'manager') as mock_manager:
            mock_manager.execute_query.return_value = []
            
            with pytest.raises(DataNotFoundError):
                await accessor.get_latest_reading()
    
    @pytest_asyncio.async_test
    async def test_get_readings_by_hours(self, mock_db_accessor):
        \"\"\"期間指定データ取得テスト\"\"\"
        
        readings = await mock_db_accessor.get_readings_by_hours(hours=3)
        
        assert len(readings) > 0
        assert all('datetime' in r for r in readings)
        assert all('co2' in r for r in readings)
        
        # 時系列順であることを確認
        timestamps = [r['datetime'] for r in readings]
        assert timestamps == sorted(timestamps)
    
    @pytest_asyncio.async_test
    async def test_get_co2_statistics(self, mock_db_accessor):
        \"\"\"CO2統計取得テスト\"\"\"
        
        stats = await mock_db_accessor.get_co2_statistics(hours=24)
        
        assert 'avg_co2' in stats
        assert 'max_co2' in stats
        assert 'min_co2' in stats
        assert 'data_points' in stats
        
        assert stats['max_co2'] >= stats['avg_co2'] >= stats['min_co2']
        assert stats['data_points'] > 0
    
    @pytest_asyncio.async_test
    async def test_database_connection_error(self, mock_settings):
        \"\"\"データベース接続エラーテスト\"\"\"
        
        accessor = AirQualityDatabaseAccessor(mock_settings)
        
        with patch.object(accessor, 'manager') as mock_manager:
            mock_manager.execute_query.side_effect = Exception(\"Connection failed\")
            
            with pytest.raises(DatabaseConnectionError):
                await accessor.get_latest_reading()
    
    @pytest.mark.parametrize(\"hours,expected_min_points\", [
        (1, 50),    # 1時間 - 最低50ポイント
        (3, 150),   # 3時間 - 最低150ポイント
        (24, 1000), # 24時間 - 最低1000ポイント
    ])
    @pytest_asyncio.async_test
    async def test_data_volume_validation(
        self, 
        mock_db_accessor, 
        hours, 
        expected_min_points
    ):
        \"\"\"データ量の妥当性テスト\"\"\"
        
        readings = await mock_db_accessor.get_readings_by_hours(hours=hours)
        
        # 期待される最小データポイント数以上であることを確認
        assert len(readings) >= expected_min_points
```

#### 2. 分析エンジンテスト
```python
import pytest
from datetime import datetime, timedelta

from analysis.co2_analysis_engine import CO2AnalysisEngine
from fixtures.sample_data import TestDataGenerator

class TestCO2AnalysisEngine:
    \"\"\"CO2AnalysisEngineのテスト\"\"\"
    
    def test_determine_status_good(self, analysis_engine):
        \"\"\"良好ステータス判定テスト\"\"\"
        
        analysis_data = {
            'high_co2_duration_minutes': 0,
            'trend': '安定',
            'co2_change_1h': 10
        }
        
        status = analysis_engine.determine_status(700, analysis_data)
        assert status == \"良好\"
    
    def test_determine_status_caution(self, analysis_engine):
        \"\"\"注意ステータス判定テスト\"\"\"
        
        analysis_data = {
            'high_co2_duration_minutes': 40,
            'trend': '上昇傾向',
            'co2_change_1h': 150
        }
        
        status = analysis_engine.determine_status(900, analysis_data)
        assert status == \"注意\"
    
    def test_determine_status_danger(self, analysis_engine):
        \"\"\"危険ステータス判定テスト\"\"\"
        
        analysis_data = {
            'high_co2_duration_minutes': 150,
            'trend': '急上昇',
            'co2_change_1h': 300
        }
        
        status = analysis_engine.determine_status(1300, analysis_data)
        assert status == \"危険\"
    
    def test_calculate_basic_trend_stable(self, analysis_engine):
        \"\"\"安定トレンド計算テスト\"\"\"
        
        # 安定したデータ生成
        readings = TestDataGenerator.generate_co2_pattern(
            hours=2, 
            pattern_type=\"normal\"
        )
        
        trend = analysis_engine.calculate_basic_trend(readings)
        
        assert 'trend' in trend
        assert 'recent_avg' in trend
        assert 'previous_avg' in trend
        assert 'change_amount' in trend
    
    def test_calculate_basic_trend_rising(self, analysis_engine):
        \"\"\"上昇トレンド計算テスト\"\"\"
        
        # 上昇パターンデータ生成
        readings = TestDataGenerator.generate_co2_pattern(
            hours=2,
            pattern_type=\"gradual_increase\"
        )
        
        trend = analysis_engine.calculate_basic_trend(readings)
        
        assert \"上昇\" in trend['trend']
        assert trend['change_amount'] > 0
    
    def test_calculate_high_co2_duration(self, analysis_engine):
        \"\"\"高CO2継続時間計算テスト\"\"\"
        
        # 高CO2データ生成
        high_co2_readings = []
        base_time = datetime.now() - timedelta(hours=1)
        
        for i in range(60):  # 1時間分
            reading = {
                'datetime': base_time + timedelta(minutes=i),
                'co2': 950 if i >= 30 else 700,  # 後半30分は高CO2
                'temperature': 23.0
            }
            high_co2_readings.append(reading)
        
        duration = analysis_engine.calculate_high_co2_duration(high_co2_readings)
        
        assert duration == 30  # 30分間継続
    
    def test_generate_message_danger(self, analysis_engine):
        \"\"\"危険レベルメッセージ生成テスト\"\"\"
        
        analysis_data = {
            'current_co2': 1400,
            'trend': '急上昇',
            'high_co2_duration_minutes': 120
        }
        
        message = analysis_engine.generate_status_message(\"危険\", analysis_data)
        
        assert \"危険\" in message or \"直ちに\" in message or \"速やかに\" in message
        assert \"1400\" in message
    
    def test_generate_recommendations_ventilation(self, analysis_engine):
        \"\"\"換気推奨アクション生成テスト\"\"\"
        
        analysis_data = {
            'current_co2': 1200,
            'current_temperature': 22,
            'trend': '上昇傾向'
        }
        
        recommendations = analysis_engine.generate_recommendations(\"危険\", analysis_data)
        
        assert len(recommendations) >= 2
        assert any(\"窓\" in rec for rec in recommendations)
        assert any(\"換気\" in rec for rec in recommendations)
    
    @pytest.mark.parametrize(\"co2_value,expected_status\", [
        (600, \"良好\"),
        (850, \"注意\"),
        (1300, \"危険\"),
    ])
    def test_status_determination_boundaries(
        self, 
        analysis_engine, 
        co2_value, 
        expected_status
    ):
        \"\"\"境界値でのステータス判定テスト\"\"\"
        
        analysis_data = {
            'high_co2_duration_minutes': 0,
            'trend': '安定',
            'co2_change_1h': 0
        }
        
        status = analysis_engine.determine_status(co2_value, analysis_data)
        assert status == expected_status
```

#### 3. Pydanticモデルテスト
```python
import pytest
from datetime import datetime
from pydantic import ValidationError

from openapi_server.models.air_quality import (
    AirQualityResponse, CurrentReading, AnalysisData, TimelinePoint
)

class TestPydanticModels:
    \"\"\"Pydanticモデルのテスト\"\"\"
    
    def test_current_reading_valid(self):
        \"\"\"CurrentReading正常値テスト\"\"\"
        
        reading = CurrentReading(
            co2=800,
            temperature=23.5,
            timestamp=datetime.now()
        )
        
        assert reading.co2 == 800
        assert reading.temperature == 23.5
        assert isinstance(reading.timestamp, datetime)
    
    def test_current_reading_invalid_co2(self):
        \"\"\"CurrentReading無効CO2値テスト\"\"\"
        
        with pytest.raises(ValidationError) as exc_info:
            CurrentReading(
                co2=-100,  # 負の値
                temperature=23.5,
                timestamp=datetime.now()
            )
        
        assert \"ensure this value is greater than or equal to 0\" in str(exc_info.value)
    
    def test_current_reading_invalid_temperature(self):
        \"\"\"CurrentReading無効温度値テスト\"\"\"
        
        with pytest.raises(ValidationError):
            CurrentReading(
                co2=800,
                temperature=200.0,  # 範囲外
                timestamp=datetime.now()
            )
    
    def test_analysis_data_valid(self):
        \"\"\"AnalysisData正常値テスト\"\"\"
        
        analysis = AnalysisData(
            period_hours=3,
            avg_co2=750.5,
            max_co2=1200,
            min_co2=450,
            trend=\"上昇傾向\",
            high_co2_duration_minutes=45,
            data_points=180
        )
        
        assert analysis.period_hours == 3
        assert analysis.trend == \"上昇傾向\"
        assert analysis.max_co2 >= analysis.avg_co2 >= analysis.min_co2
    
    def test_analysis_data_invalid_trend(self):
        \"\"\"AnalysisData無効トレンド値テスト\"\"\"
        
        with pytest.raises(ValidationError):
            AnalysisData(
                period_hours=3,
                avg_co2=750.5,
                max_co2=1200,
                min_co2=450,
                trend=\"無効なトレンド\",  # Literalで定義されていない値
                high_co2_duration_minutes=45,
                data_points=180
            )
    
    def test_air_quality_response_complete(self):
        \"\"\"AirQualityResponse完全レスポンステスト\"\"\"
        
        current = CurrentReading(
            co2=950,
            temperature=23.5,
            timestamp=datetime.now()
        )
        
        analysis = AnalysisData(
            period_hours=3,
            avg_co2=780.5,
            max_co2=1200,
            min_co2=450,
            trend=\"上昇傾向\",
            high_co2_duration_minutes=45,
            data_points=180
        )
        
        response = AirQualityResponse(
            status=\"注意\",
            current=current,
            analysis=analysis,
            message=\"CO2濃度が上昇傾向です\",
            action=\"換気推奨\",
            recommendations=[\"窓を開けてください\", \"30分後に確認してください\"]
        )
        
        assert response.status == \"注意\"
        assert response.action == \"換気推奨\"
        assert len(response.recommendations) == 2
        assert response.generated_at is not None
    
    def test_timeline_validation(self):
        \"\"\"タイムライン検証テスト\"\"\"
        
        # 大量データのテスト
        large_timeline = [
            TimelinePoint(
                timestamp=datetime.now(),
                co2=800,
                temperature=23.0
            ) for _ in range(1001)  # 制限超過
        ]
        
        current = CurrentReading(co2=800, temperature=23.0, timestamp=datetime.now())
        analysis = AnalysisData(
            period_hours=3, avg_co2=800, max_co2=850, min_co2=750,
            trend=\"安定\", high_co2_duration_minutes=0, data_points=180
        )
        
        with pytest.raises(ValidationError) as exc_info:
            AirQualityResponse(
                status=\"良好\",
                current=current,
                analysis=analysis,
                message=\"テスト\",
                action=\"問題なし\",
                recommendations=[\"維持してください\"],
                timeline=large_timeline
            )
        
        assert \"Timeline data too large\" in str(exc_info.value)
```

### パフォーマンステスト

#### 1. APIレスポンス時間テスト
```python
import pytest
import time
from fastapi.testclient import TestClient

class TestPerformance:
    \"\"\"パフォーマンステスト\"\"\"
    
    @pytest.mark.asyncio
    async def test_api_response_time(self, test_app):
        \"\"\"APIレスポンス時間テスト\"\"\"
        
        with TestClient(test_app) as client:
            start_time = time.time()
            
            response = client.get(\"/api/air-quality/co2-status?hours=3\")
            
            end_time = time.time()
            response_time = end_time - start_time
            
            assert response.status_code == 200
            assert response_time < 2.0  # 2秒以内
    
    @pytest.mark.asyncio
    async def test_large_dataset_performance(self, analysis_engine):
        \"\"\"大量データ処理パフォーマンステスト\"\"\"
        
        # 24時間分の大量データ
        large_dataset = TestDataGenerator.generate_co2_pattern(
            hours=24, 
            interval_minutes=1
        )
        
        start_time = time.time()
        
        trend = analysis_engine.calculate_basic_trend(large_dataset)
        duration = analysis_engine.calculate_high_co2_duration(large_dataset)
        
        end_time = time.time()
        processing_time = end_time - start_time
        
        assert processing_time < 1.0  # 1秒以内
        assert trend is not None
        assert duration >= 0
    
    @pytest.mark.parametrize(\"data_size,max_time\", [
        (60, 0.1),    # 1時間 - 0.1秒以内
        (360, 0.3),   # 6時間 - 0.3秒以内
        (1440, 1.0),  # 24時間 - 1秒以内
    ])
    def test_analysis_scalability(self, analysis_engine, data_size, max_time):
        \"\"\"分析処理のスケーラビリティテスト\"\"\"
        
        dataset = TestDataGenerator.generate_co2_pattern(
            hours=data_size//60,
            interval_minutes=1
        )
        
        start_time = time.time()
        analysis_engine.calculate_basic_trend(dataset)
        processing_time = time.time() - start_time
        
        assert processing_time < max_time
```

## ✅ 完了条件
- [ ] 全単体テストの実装
- [ ] テストカバレッジ90%以上
- [ ] モックとフィクスチャの整備
- [ ] パフォーマンステストの実装
- [ ] CI/CD統合テストの設定
- [ ] テストドキュメント

## 🧪 テスト実行とカバレッジ
```bash
# 全テスト実行
pytest tests/ -v

# カバレッジ付きテスト実行
pytest tests/ --cov=src --cov-report=html --cov-report=term

# 特定カテゴリのテスト
pytest tests/unit/ -v
pytest tests/integration/ -v
pytest tests/performance/ -v

# パフォーマンステストのみ
pytest tests/performance/ -v --benchmark-only
```

## 📁 ファイル構成
```
tests/
├── conftest.py                      # 完全実装
├── unit/
│   ├── test_bigquery_client.py      # 新規作成
│   ├── test_air_quality_accessor.py # 新規作成
│   ├── test_co2_analysis_engine.py  # 新規作成
│   ├── test_pydantic_models.py      # 新規作成
│   └── test_error_handling.py       # 新規作成
├── integration/
│   ├── test_api_endpoints.py        # 新規作成
│   └── test_database_integration.py # 新規作成
├── performance/
│   └── test_performance.py          # 新規作成
└── fixtures/
    ├── sample_data.py               # 新規作成
    └── mock_responses.py            # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #9 エラーハンドリングと入力検証
- 次のIssue: #11 Cloud Run対応とデプロイ設定

## 🎯 テスト戦略
- **単体テスト**: 各コンポーネントの独立テスト
- **統合テスト**: コンポーネント間の連携テスト
- **パフォーマンステスト**: レスポンス時間とスケーラビリティ
- **回帰テスト**: 継続的な品質保証