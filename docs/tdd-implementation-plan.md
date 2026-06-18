# TDD実装計画

## 🎯 概要
Test-Driven Development (TDD) アプローチでCO2モニタリングAPIを実装するための包括的な計画

## 📋 TDD基本フロー
1. **Red**: 失敗するテストを書く
2. **Green**: テストが通る最小限のコードを書く
3. **Refactor**: コードを改善する

## 🏗️ 依存性注入設計

### 1. データベース抽象化層
```python
# src/database/interfaces.py
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from datetime import datetime

class DatabaseInterface(ABC):
    """データベース抽象インターフェース"""
    
    @abstractmethod
    async def execute_query(self, query: str, params: dict = None) -> List[Dict[str, Any]]:
        """クエリ実行"""
        pass
    
    @abstractmethod
    async def get_latest_reading(self) -> Dict[str, Any]:
        """最新測定値取得"""
        pass
    
    @abstractmethod
    async def get_readings_by_hours(self, hours: int) -> List[Dict[str, Any]]:
        """期間指定データ取得"""
        pass
    
    @abstractmethod
    async def get_co2_statistics(self, hours: int) -> Dict[str, float]:
        """CO2統計取得"""
        pass
    
    @abstractmethod
    async def close(self):
        """接続クローズ"""
        pass

class BigQueryRepository(DatabaseInterface):
    """BigQuery実装"""
    
    def __init__(self, project_id: str, dataset: str, table: str):
        self.project_id = project_id
        self.dataset = dataset
        self.table = table
        self.client = None  # 実装時に初期化
    
    async def execute_query(self, query: str, params: dict = None) -> List[Dict[str, Any]]:
        # BigQuery実装
        pass
    
    async def get_latest_reading(self) -> Dict[str, Any]:
        query = f"""
        SELECT datetime, temperature, co2, data
        FROM `{self.project_id}.{self.dataset}.{self.table}`
        ORDER BY datetime DESC
        LIMIT 1
        """
        results = await self.execute_query(query)
        if not results:
            raise DataNotFoundError("No readings available")
        return results[0]
    
    # 他のメソッドも実装...

class SQLiteRepository(DatabaseInterface):
    """SQLite実装（テスト用）"""
    
    def __init__(self, db_path: str = ":memory:"):
        self.db_path = db_path
        self.connection = None
    
    async def execute_query(self, query: str, params: dict = None) -> List[Dict[str, Any]]:
        # SQLite実装
        pass
    
    async def get_latest_reading(self) -> Dict[str, Any]:
        query = """
        SELECT datetime, temperature, co2, data
        FROM bedroom_co2
        ORDER BY datetime DESC
        LIMIT 1
        """
        results = await self.execute_query(query)
        if not results:
            raise DataNotFoundError("No readings available")
        return results[0]
    
    # 他のメソッドも実装...
```

### 2. 依存性注入コンテナ
```python
# src/dependencies/container.py
from typing import Protocol, runtime_checkable
from dataclasses import dataclass
import os

@runtime_checkable
class SettingsProtocol(Protocol):
    """設定プロトコル"""
    USE_BIGQUERY: bool
    PROJECT_ID: str
    BIGQUERY_DATASET: str
    BIGQUERY_TABLE: str
    SQLITE_PATH: str

@dataclass
class Dependencies:
    """依存性コンテナ"""
    database: DatabaseInterface
    settings: SettingsProtocol

class DependencyInjector:
    """依存性注入器"""
    
    @staticmethod
    def create_database(settings: SettingsProtocol) -> DatabaseInterface:
        """環境に応じたデータベース実装を生成"""
        
        if settings.USE_BIGQUERY:
            return BigQueryRepository(
                project_id=settings.PROJECT_ID,
                dataset=settings.BIGQUERY_DATASET,
                table=settings.BIGQUERY_TABLE
            )
        else:
            return SQLiteRepository(db_path=settings.SQLITE_PATH)
    
    @staticmethod
    def create_dependencies(settings: SettingsProtocol) -> Dependencies:
        """依存性一式を生成"""
        
        database = DependencyInjector.create_database(settings)
        
        return Dependencies(
            database=database,
            settings=settings
        )

# FastAPI依存性注入
from fastapi import Depends

def get_settings() -> SettingsProtocol:
    """設定取得"""
    if os.getenv("TESTING") == "true":
        return TestSettings()
    else:
        return ProductionSettings()

def get_dependencies(settings: SettingsProtocol = Depends(get_settings)) -> Dependencies:
    """依存性取得"""
    return DependencyInjector.create_dependencies(settings)
```

## 🧪 TDD用テストケース設計

### Phase 1: データベース層（Red-Green-Refactor）

#### Test Case 1: SQLite Repository
```python
# tests/unit/test_sqlite_repository.py
import pytest
import pytest_asyncio
from datetime import datetime, timedelta

class TestSQLiteRepository:
    """SQLiteRepository TDDテスト"""
    
    @pytest_asyncio.fixture
    async def repository(self):
        """テスト用リポジトリ"""
        repo = SQLiteRepository(":memory:")
        await repo.setup_tables()
        yield repo
        await repo.close()
    
    @pytest_asyncio.fixture
    async def sample_data(self, repository):
        """サンプルデータ投入"""
        data = [
            {
                'datetime': datetime.now() - timedelta(minutes=10),
                'temperature': 23.5,
                'co2': 800,
                'data': None
            },
            {
                'datetime': datetime.now() - timedelta(minutes=5),
                'temperature': 23.8,
                'co2': 850,
                'data': None
            },
            {
                'datetime': datetime.now(),
                'temperature': 24.0,
                'co2': 900,
                'data': None
            }
        ]
        
        for item in data:
            await repository.insert_reading(item)
        
        return data
    
    # Red: 最初は失敗するテスト
    @pytest_asyncio.async_test
    async def test_get_latest_reading_when_no_data(self, repository):
        """データなしの場合の最新読み取りテスト（Red）"""
        
        with pytest.raises(DataNotFoundError):
            await repository.get_latest_reading()
    
    # Green: テストが通る最小実装
    @pytest_asyncio.async_test
    async def test_get_latest_reading_success(self, repository, sample_data):
        """最新読み取り成功テスト（Green）"""
        
        result = await repository.get_latest_reading()
        
        assert result is not None
        assert result['co2'] == 900  # 最新データ
        assert result['temperature'] == 24.0
    
    # Refactor: 実装改善後のテスト
    @pytest_asyncio.async_test
    async def test_get_readings_by_hours(self, repository, sample_data):
        """期間指定データ取得テスト"""
        
        readings = await repository.get_readings_by_hours(1)  # 1時間分
        
        assert len(readings) == 3
        assert all('co2' in r for r in readings)
        # 時系列順であることを確認
        timestamps = [r['datetime'] for r in readings]
        assert timestamps == sorted(timestamps)
    
    @pytest_asyncio.async_test
    async def test_get_co2_statistics(self, repository, sample_data):
        """統計計算テスト"""
        
        stats = await repository.get_co2_statistics(1)
        
        assert stats['avg_co2'] == 850.0  # (800+850+900)/3
        assert stats['max_co2'] == 900
        assert stats['min_co2'] == 800
        assert stats['data_points'] == 3
```

#### Test Case 2: 分析エンジン
```python
# tests/unit/test_co2_analysis_engine.py
class TestCO2AnalysisEngine:
    """分析エンジンTDDテスト"""
    
    def test_determine_status_good_level(self):
        """良好レベル判定テスト（Red → Green → Refactor）"""
        
        # Red: 最初は実装がないので失敗
        engine = CO2AnalysisEngine()
        
        # Green: 最小実装でテスト通す
        analysis_data = {
            'high_co2_duration_minutes': 0,
            'trend': '安定',
            'co2_change_1h': 10
        }
        
        status = engine.determine_status(700, analysis_data)
        assert status == "良好"
    
    def test_determine_status_caution_level(self):
        """注意レベル判定テスト"""
        
        engine = CO2AnalysisEngine()
        analysis_data = {
            'high_co2_duration_minutes': 40,
            'trend': '上昇傾向',
            'co2_change_1h': 150
        }
        
        status = engine.determine_status(900, analysis_data)
        assert status == "注意"
    
    def test_determine_status_danger_level(self):
        """危険レベル判定テスト"""
        
        engine = CO2AnalysisEngine()
        analysis_data = {
            'high_co2_duration_minutes': 150,
            'trend': '急上昇',
            'co2_change_1h': 300
        }
        
        status = engine.determine_status(1300, analysis_data)
        assert status == "危険"
    
    @pytest.mark.parametrize("co2,expected", [
        (600, "良好"),
        (750, "良好"),
        (800, "注意"),  # 境界値
        (950, "注意"),
        (1200, "危険"),  # 境界値
        (1500, "危険")
    ])
    def test_status_boundary_values(self, co2, expected):
        """境界値テスト"""
        
        engine = CO2AnalysisEngine()
        analysis_data = {
            'high_co2_duration_minutes': 0,
            'trend': '安定',
            'co2_change_1h': 0
        }
        
        status = engine.determine_status(co2, analysis_data)
        assert status == expected
```

### Phase 2: 統合テスト

#### Test Case 3: API エンドポイント
```python
# tests/integration/test_api_endpoints.py
class TestCO2StatusAPI:
    """CO2ステータスAPI統合テスト"""
    
    @pytest.fixture
    def test_app(self):
        """テスト用アプリケーション"""
        from openapi_server.main import app
        
        # テスト用依存性注入
        app.dependency_overrides[get_dependencies] = self.get_test_dependencies
        
        yield app
        
        # クリーンアップ
        app.dependency_overrides.clear()
    
    def get_test_dependencies(self):
        """テスト用依存性"""
        settings = TestSettings()
        return DependencyInjector.create_dependencies(settings)
    
    @pytest_asyncio.async_test
    async def test_co2_status_endpoint_success(self, test_app):
        """CO2ステータス正常取得テスト"""
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/air-quality/co2-status?hours=3")
            
            assert response.status_code == 200
            
            data = response.json()
            assert "status" in data
            assert "current" in data
            assert "analysis" in data
            assert "message" in data
            assert "recommendations" in data
    
    @pytest_asyncio.async_test
    async def test_co2_status_no_data_error(self, test_app):
        """データなしエラーテスト"""
        
        # 空のデータベースでテスト
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            response = await client.get("/api/air-quality/co2-status?hours=3")
            
            assert response.status_code == 404
            
            error = response.json()
            assert error["error"]["code"] == "DATA_NOT_FOUND"
    
    @pytest_asyncio.async_test
    async def test_co2_status_invalid_params(self, test_app):
        """無効パラメータテスト"""
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # 負の値
            response = await client.get("/api/air-quality/co2-status?hours=-1")
            assert response.status_code == 422
            
            # 範囲外の値
            response = await client.get("/api/air-quality/co2-status?hours=200")
            assert response.status_code == 422
```

## 🔄 TDD実装順序

### Step 1: Red-Green-Refactor サイクル 1
1. **Red**: `test_sqlite_repository.py` - 基本的なデータアクセステスト
2. **Green**: `SQLiteRepository` - 最小実装
3. **Refactor**: コード改善、重複排除

### Step 2: Red-Green-Refactor サイクル 2
1. **Red**: `test_co2_analysis_engine.py` - 分析ロジックテスト
2. **Green**: `CO2AnalysisEngine` - 最小実装
3. **Refactor**: アルゴリズム改善

### Step 3: Red-Green-Refactor サイクル 3
1. **Red**: `test_api_endpoints.py` - API統合テスト
2. **Green**: APIエンドポイント実装
3. **Refactor**: エラーハンドリング、パフォーマンス改善

### Step 4: Red-Green-Refactor サイクル 4
1. **Red**: `test_bigquery_repository.py` - BigQuery実装テスト
2. **Green**: `BigQueryRepository` - 本番実装
3. **Refactor**: 最適化、キャッシュ実装

## 🧪 テスト設定ファイル

### pytest.ini
```ini
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = 
    -v
    --tb=short
    --strict-markers
    --disable-warnings
    --cov=src
    --cov-report=term-missing
    --cov-report=html:htmlcov
    --cov-fail-under=80

markers =
    unit: Unit tests
    integration: Integration tests
    performance: Performance tests
    slow: Slow running tests
    
asyncio_mode = auto
```

### conftest.py（テスト共通設定）
```python
# tests/conftest.py
import pytest
import pytest_asyncio
from datetime import datetime, timedelta
import os

# テスト環境設定
os.environ["TESTING"] = "true"
os.environ["USE_BIGQUERY"] = "false"
os.environ["SQLITE_PATH"] = ":memory:"

@pytest.fixture(scope="session")
def test_settings():
    """テスト設定"""
    from src.config.test_settings import TestSettings
    return TestSettings()

@pytest_asyncio.fixture
async def test_database(test_settings):
    """テスト用データベース"""
    from src.database.sqlite_repository import SQLiteRepository
    
    db = SQLiteRepository(":memory:")
    await db.setup_tables()
    
    yield db
    
    await db.close()

@pytest.fixture
def sample_co2_data():
    """サンプルCO2データ"""
    base_time = datetime.now() - timedelta(hours=3)
    
    data = []
    for i in range(180):  # 3時間分、1分間隔
        timestamp = base_time + timedelta(minutes=i)
        
        # パターン: 最初は低く、徐々に上昇
        if i < 60:
            co2 = 450 + i * 2
        elif i < 120:
            co2 = 570 + (i - 60) * 5
        else:
            co2 = 870 + (i - 120) * 3
        
        data.append({
            'datetime': timestamp,
            'temperature': 22.0 + (i * 0.01),
            'co2': int(co2),
            'data': None
        })
    
    return data

@pytest_asyncio.fixture
async def populated_test_database(test_database, sample_co2_data):
    """データ投入済みテストDB"""
    
    for item in sample_co2_data:
        await test_database.insert_reading(item)
    
    return test_database
```

## 📊 TDD進捗管理

### テストカバレッジ目標
- **Unit Tests**: 95%以上
- **Integration Tests**: 80%以上
- **End-to-End Tests**: 主要パス100%

### TDD実装チェックリスト
- [ ] **Step 1**: SQLiteRepository TDD実装
- [ ] **Step 2**: CO2AnalysisEngine TDD実装
- [ ] **Step 3**: API Endpoints TDD実装
- [ ] **Step 4**: BigQueryRepository TDD実装
- [ ] **Step 5**: 統合テスト完了
- [ ] **Step 6**: パフォーマンステスト実装

### コードレビュー観点
1. **テストファースト**: 実装前にテストが書かれているか
2. **最小実装**: Greenフェーズで過剰実装していないか
3. **リファクタリング**: Refactorフェーズで適切な改善がされているか
4. **テスト品質**: テストが実装の品質を保証しているか
5. **依存性注入**: 適切にDIが実装されているか