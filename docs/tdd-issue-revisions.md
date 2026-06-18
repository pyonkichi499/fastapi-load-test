# TDD対応Issue修正版

## 📋 概要
TDD(Test-Driven Development)アプローチに対応するため、依存性注入とテスタビリティを重視したIssue修正版

## 🔄 修正が必要なIssue

### Issue #1 修正版: データベース抽象化層の実装

#### 修正前（BigQuery直接実装）
```python
class BigQueryClient:
    def __init__(self, project_id: str = "monitoring-bedroom")
```

#### 修正後（インターフェース分離）
```python
# src/database/interfaces.py
from abc import ABC, abstractmethod

class DatabaseInterface(ABC):
    """データベース抽象インターフェース"""
    
    @abstractmethod
    async def get_latest_reading(self) -> Dict[str, Any]:
        pass
    
    @abstractmethod
    async def get_readings_by_hours(self, hours: int) -> List[Dict[str, Any]]:
        pass

# TDD実装順序
# 1. Red: インターフェーステスト作成
# 2. Green: SQLite実装でテスト通す
# 3. Refactor: BigQuery実装追加
```

### Issue #3 修正版: TDD用テストデータベース

#### 修正内容
```python
# src/database/test_database.py
class TestDatabaseManager:
    """TDD用テストデータベース管理"""
    
    @staticmethod
    async def create_test_database() -> SQLiteRepository:
        """テスト用データベース作成"""
        
        db = SQLiteRepository(":memory:")
        await db.setup_tables()
        
        # テーブル作成SQL
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS bedroom_co2 (
            datetime TIMESTAMP NOT NULL,
            temperature REAL NOT NULL,
            co2 INTEGER NOT NULL,
            data TEXT,
            PRIMARY KEY (datetime)
        );
        """
        
        await db.execute_query(create_table_sql)
        return db
    
    @staticmethod
    async def populate_test_data(
        db: SQLiteRepository,
        pattern: str = "normal",
        hours: int = 3
    ):
        """テストデータ投入"""
        
        data_generator = TestDataGenerator()
        sample_data = data_generator.generate_co2_pattern(
            hours=hours,
            pattern_type=pattern
        )
        
        for item in sample_data:
            await db.insert_reading(item)
        
        return sample_data

# TDD実装順序
# 1. Red: テストデータ投入・取得テスト
# 2. Green: SQLite基本機能実装
# 3. Refactor: データ生成パターン改善
```

### Issue #4 修正版: 依存性注入対応データアクセサー

#### 修正内容
```python
# src/services/air_quality_service.py
class AirQualityService:
    """ビジネスロジック層（依存性注入対応）"""
    
    def __init__(self, database: DatabaseInterface):
        self.database = database
        self.analysis_engine = CO2AnalysisEngine()
    
    async def get_air_quality_status(
        self, 
        hours: int = 3,
        include_timeline: bool = True
    ) -> AirQualityResponse:
        """空気質ステータス取得（DI版）"""
        
        # データ取得（抽象化されたインターフェース使用）
        latest_reading = await self.database.get_latest_reading()
        readings = await self.database.get_readings_by_hours(hours)
        statistics = await self.database.get_co2_statistics(hours)
        
        # 分析処理
        return await self._analyze_and_build_response(
            latest_reading, readings, statistics, include_timeline
        )

# TDD実装順序
# 1. Red: サービス層テスト（モック使用）
# 2. Green: 最小限のサービス実装
# 3. Refactor: エラーハンドリング追加
```

### Issue #8 修正版: DI対応API実装

#### 修正内容
```python
# src/openapi_server/apis/air_quality_api.py
from fastapi import APIRouter, Depends, HTTPException, Query

router = APIRouter(prefix="/api/air-quality", tags=["air-quality"])

@router.get("/co2-status", response_model=AirQualityResponse)
async def get_co2_status(
    hours: int = Query(3, description="分析期間（時間）", ge=1, le=168),
    include_timeline: bool = Query(True, description="時系列データを含めるか"),
    service: AirQualityService = Depends(get_air_quality_service)  # DI
):
    """CO2ステータス取得（DI版）"""
    
    try:
        result = await service.get_air_quality_status(
            hours=hours,
            include_timeline=include_timeline
        )
        return result
        
    except DataNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    
    except Exception as e:
        logger.error(f"Unexpected error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error")

# 依存性注入関数
def get_air_quality_service(
    dependencies: Dependencies = Depends(get_dependencies)
) -> AirQualityService:
    """AirQualityService依存性注入"""
    return AirQualityService(database=dependencies.database)

# TDD実装順序
# 1. Red: APIエンドポイントテスト（モック使用）
# 2. Green: 基本的なエンドポイント実装
# 3. Refactor: エラーハンドリング充実
```

## 🧪 TDD対応テスト設計

### Phase 1: データベース層TDD

#### Test Case 1.1: データベースインターフェース
```python
# tests/unit/test_database_interface.py
class TestDatabaseInterface:
    """データベースインターフェーステスト"""
    
    @pytest_asyncio.fixture
    async def sqlite_db(self):
        """SQLite実装テスト用"""
        db = await TestDatabaseManager.create_test_database()
        yield db
        await db.close()
    
    @pytest_asyncio.async_test
    async def test_get_latest_reading_interface(self, sqlite_db):
        """最新読み取りインターフェーステスト（Red）"""
        
        # Red: データなしでエラーになることを確認
        with pytest.raises(DataNotFoundError):
            await sqlite_db.get_latest_reading()
    
    @pytest_asyncio.async_test
    async def test_get_latest_reading_with_data(self, sqlite_db):
        """データありでの最新読み取りテスト（Green）"""
        
        # テストデータ投入
        test_data = [{
            'datetime': datetime.now(),
            'temperature': 23.5,
            'co2': 800,
            'data': None
        }]
        
        await TestDatabaseManager.populate_test_data(sqlite_db, test_data)
        
        # Green: データが正しく取得できることを確認
        result = await sqlite_db.get_latest_reading()
        assert result['co2'] == 800
        assert result['temperature'] == 23.5
```

#### Test Case 1.2: 実装別テスト
```python
# tests/unit/test_sqlite_repository.py
class TestSQLiteRepository:
    """SQLiteRepository実装テスト"""
    
    @pytest_asyncio.async_test
    async def test_create_tables(self):
        """テーブル作成テスト（Red → Green）"""
        
        # Red: テーブルが存在しない状態
        db = SQLiteRepository(":memory:")
        
        # Green: テーブル作成機能実装
        await db.setup_tables()
        
        # テーブル存在確認
        tables = await db.get_table_list()
        assert "bedroom_co2" in tables
    
    @pytest_asyncio.async_test
    async def test_insert_and_retrieve(self):
        """データ挿入・取得テスト（Red → Green → Refactor）"""
        
        db = await TestDatabaseManager.create_test_database()
        
        # Red: 空のDBでは0件
        count = await db.count_records()
        assert count == 0
        
        # Green: データ挿入機能実装
        test_reading = {
            'datetime': datetime.now(),
            'temperature': 22.0,
            'co2': 750,
            'data': None
        }
        
        await db.insert_reading(test_reading)
        
        # データ取得確認
        count = await db.count_records()
        assert count == 1
        
        retrieved = await db.get_latest_reading()
        assert retrieved['co2'] == 750
        
        await db.close()
```

### Phase 2: サービス層TDD

#### Test Case 2.1: AirQualityService
```python
# tests/unit/test_air_quality_service.py
class TestAirQualityService:
    """AirQualityServiceテスト"""
    
    @pytest.fixture
    def mock_database(self):
        """モックデータベース"""
        mock_db = AsyncMock(spec=DatabaseInterface)
        
        # モック設定
        mock_db.get_latest_reading.return_value = {
            'datetime': datetime.now(),
            'temperature': 23.5,
            'co2': 850,
            'data': None
        }
        
        mock_db.get_readings_by_hours.return_value = [
            # 3時間分のテストデータ
        ]
        
        mock_db.get_co2_statistics.return_value = {
            'avg_co2': 780.5,
            'max_co2': 1200,
            'min_co2': 450,
            'data_points': 180
        }
        
        return mock_db
    
    @pytest_asyncio.async_test
    async def test_get_air_quality_status_success(self, mock_database):
        """正常系テスト（Red → Green）"""
        
        # Red: サービスクラスが存在しない
        service = AirQualityService(database=mock_database)
        
        # Green: 基本的な処理実装
        result = await service.get_air_quality_status(hours=3)
        
        assert isinstance(result, AirQualityResponse)
        assert result.status in ["良好", "注意", "危険"]
        assert result.current.co2 == 850
        
        # モック呼び出し確認
        mock_database.get_latest_reading.assert_called_once()
        mock_database.get_readings_by_hours.assert_called_once_with(3)
        mock_database.get_co2_statistics.assert_called_once_with(3)
    
    @pytest_asyncio.async_test
    async def test_get_air_quality_status_no_data(self, mock_database):
        """データなしエラーテスト（Red → Green）"""
        
        # Red: エラーハンドリングなし
        mock_database.get_latest_reading.side_effect = DataNotFoundError("No data")
        
        service = AirQualityService(database=mock_database)
        
        # Green: エラーハンドリング実装
        with pytest.raises(DataNotFoundError):
            await service.get_air_quality_status(hours=3)
```

### Phase 3: API層TDD

#### Test Case 3.1: APIエンドポイント
```python
# tests/integration/test_co2_api_endpoints.py
class TestCO2APIEndpoints:
    """CO2 API統合テスト"""
    
    @pytest.fixture
    def test_app(self):
        """テスト用アプリ"""
        from openapi_server.main import create_app
        
        app = create_app()
        
        # テスト用依存性注入
        def get_test_service():
            test_db = AsyncMock(spec=DatabaseInterface)
            return AirQualityService(database=test_db)
        
        app.dependency_overrides[get_air_quality_service] = get_test_service
        
        yield app
        
        app.dependency_overrides.clear()
    
    @pytest_asyncio.async_test
    async def test_co2_status_endpoint_integration(self, test_app):
        """CO2ステータスエンドポイント統合テスト（Red → Green）"""
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # Red: エンドポイントが存在しない
            response = await client.get("/api/air-quality/co2-status?hours=3")
            
            # Green: 基本的なエンドポイント実装
            assert response.status_code == 200
            
            data = response.json()
            assert "status" in data
            assert "current" in data
            assert "analysis" in data
    
    @pytest_asyncio.async_test
    async def test_co2_status_validation_error(self, test_app):
        """バリデーションエラーテスト"""
        
        async with AsyncClient(app=test_app, base_url="http://test") as client:
            # 無効パラメータ
            response = await client.get("/api/air-quality/co2-status?hours=-1")
            assert response.status_code == 422
            
            response = await client.get("/api/air-quality/co2-status?hours=200")
            assert response.status_code == 422
```

## 🔄 TDD実装サイクル詳細

### Cycle 1: データベース層
```bash
# Red Phase
pytest tests/unit/test_database_interface.py::test_get_latest_reading_interface -v
# → FAILED (実装なし)

# Green Phase
# 最小限のSQLiteRepository実装
pytest tests/unit/test_database_interface.py::test_get_latest_reading_interface -v
# → PASSED

# Refactor Phase
# コード改善、重複削除
pytest tests/unit/test_sqlite_repository.py -v
# → ALL PASSED
```

### Cycle 2: サービス層
```bash
# Red Phase
pytest tests/unit/test_air_quality_service.py::test_get_air_quality_status_success -v
# → FAILED (実装なし)

# Green Phase
# 最小限のAirQualityService実装
pytest tests/unit/test_air_quality_service.py::test_get_air_quality_status_success -v
# → PASSED

# Refactor Phase
# エラーハンドリング、ログ追加
pytest tests/unit/test_air_quality_service.py -v
# → ALL PASSED
```

### Cycle 3: API層
```bash
# Red Phase
pytest tests/integration/test_co2_api_endpoints.py::test_co2_status_endpoint_integration -v
# → FAILED (実装なし)

# Green Phase
# 基本的なAPIエンドポイント実装
pytest tests/integration/test_co2_api_endpoints.py::test_co2_status_endpoint_integration -v
# → PASSED

# Refactor Phase
# バリデーション、エラーハンドリング強化
pytest tests/integration/test_co2_api_endpoints.py -v
# → ALL PASSED
```

## 📊 TDD進捗追跡

### テストカバレッジ目標
```bash
# 全体カバレッジ確認
pytest --cov=src --cov-report=html --cov-report=term

# カバレッジ目標
# - Unit Tests: 95%以上
# - Integration Tests: 80%以上
# - Overall: 90%以上
```

### TDD品質メトリクス
1. **Test First Rate**: 実装前にテストが書かれた割合
2. **Red-Green-Refactor Cycles**: 完了したサイクル数
3. **Test Coverage**: コードカバレッジ
4. **Refactoring Frequency**: リファクタリング実施頻度
5. **Bug Detection Rate**: テストによるバグ検出率

この設計に従って、TDDアプローチで段階的に実装を進めることで、高品質で保守性の高いCO2モニタリングAPIを構築できます。