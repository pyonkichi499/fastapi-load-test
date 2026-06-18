# 快適度スコアAPI実装手順

## 概要
部屋の温度と湿度から快適度（不快指数）を計算し、時間帯別の快適度をスコア化するAPIです。

## ブランチ作成
```bash
git checkout develop
git pull origin develop
git checkout -b feature/api-comfort-score
```

## 実装手順

### 1. レスポンスモデルの作成
`src/openapi_server/models/comfort_score.py`:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ComfortDataPoint(BaseModel):
    timestamp: datetime
    temperature: float
    humidity: Optional[float]
    discomfort_index: Optional[float]
    comfort_score: int  # 0-100

class ComfortScoreResponse(BaseModel):
    room_name: str
    start_time: datetime
    end_time: datetime
    data_points: List[ComfortDataPoint]
    average_score: float
    comfort_level: str  # "快適", "やや不快", "不快", "非常に不快"
```

### 2. API実装クラスの作成
`src/openapi_server/impl/comfort_api_impl.py`:
```python
from datetime import datetime, timedelta
from typing import Optional
from fastapi import HTTPException

from openapi_server.apis.comfort_api_base import BaseComfortApi
from database.accessor import DatabaseAccessor
from database.config import get_db_settings
from openapi_server.models.comfort_score import ComfortScoreResponse, ComfortDataPoint

class ComfortApiImpl(BaseComfortApi):
    def __init__(self):
        self.settings = get_db_settings()
        self.db_accessor = DatabaseAccessor(self.settings)
    
    def calculate_discomfort_index(self, temp: float, humidity: Optional[float]) -> Optional[float]:
        """不快指数の計算
        DI = 0.81 * T + 0.01 * H * (0.99 * T - 14.3) + 46.3
        """
        if humidity is None:
            return None
        return 0.81 * temp + 0.01 * humidity * (0.99 * temp - 14.3) + 46.3
    
    def di_to_comfort_score(self, di: Optional[float]) -> int:
        """不快指数を快適度スコア(0-100)に変換"""
        if di is None:
            return 50  # デフォルト値
        
        # DI: 55以下=100点, 85以上=0点
        if di <= 55:
            return 100
        elif di >= 85:
            return 0
        else:
            # 線形補間
            return int(100 - (di - 55) * 100 / 30)
    
    def get_comfort_level(self, score: float) -> str:
        """平均スコアから快適レベルを判定"""
        if score >= 80:
            return "快適"
        elif score >= 60:
            return "やや不快"
        elif score >= 40:
            return "不快"
        else:
            return "非常に不快"
    
    async def get_comfort_score(
        self,
        room_name: str,
        hours: int = 24,
        start_time: Optional[datetime] = None,
        end_time: Optional[datetime] = None
    ) -> ComfortScoreResponse:
        """指定期間の快適度スコアを取得"""
        
        # 期間の設定
        if start_time is None:
            end_time = datetime.now()
            start_time = end_time - timedelta(hours=hours)
        elif end_time is None:
            end_time = start_time + timedelta(hours=hours)
        
        # データ取得
        try:
            records = await self.db_accessor.fetch_records(
                table_name="room_temperature",
                columns=["timestamp", "temperature", "humidity"],
                filters={
                    "room_name": room_name,
                    # 注意: 日時フィルタは現在のDatabaseAccessorでは直接サポートされていない
                    # 一旦全データを取得してPython側でフィルタリング
                },
                order_by=[("timestamp", "DESC")]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        if not records:
            raise HTTPException(status_code=404, detail=f"No data found for room: {room_name}")
        
        # 期間でフィルタリング（Python側）
        filtered_records = [
            r for r in records
            if start_time <= r["timestamp"] <= end_time
        ]
        
        if not filtered_records:
            raise HTTPException(
                status_code=404, 
                detail=f"No data found for the specified period"
            )
        
        # 快適度計算
        data_points = []
        total_score = 0
        
        for record in filtered_records:
            di = self.calculate_discomfort_index(
                record["temperature"],
                record.get("humidity")
            )
            score = self.di_to_comfort_score(di)
            
            data_points.append(ComfortDataPoint(
                timestamp=record["timestamp"],
                temperature=record["temperature"],
                humidity=record.get("humidity"),
                discomfort_index=di,
                comfort_score=score
            ))
            
            total_score += score
        
        average_score = total_score / len(data_points)
        
        return ComfortScoreResponse(
            room_name=room_name,
            start_time=start_time,
            end_time=end_time,
            data_points=data_points,
            average_score=average_score,
            comfort_level=self.get_comfort_level(average_score)
        )
```

### 3. APIルートの追加
`src/openapi_server/apis/comfort_api.py`:
```python
from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Query, Path

from openapi_server.impl.comfort_api_impl import ComfortApiImpl
from openapi_server.models.comfort_score import ComfortScoreResponse

router = APIRouter(prefix="/api", tags=["comfort"])
api_impl = ComfortApiImpl()

@router.get("/comfort-score/{room_name}", response_model=ComfortScoreResponse)
async def get_comfort_score(
    room_name: str = Path(..., description="部屋の名前"),
    hours: int = Query(24, description="取得する時間数", ge=1, le=168),
    start_time: Optional[datetime] = Query(None, description="開始時刻"),
    end_time: Optional[datetime] = Query(None, description="終了時刻")
):
    """指定された部屋の快適度スコアを取得します"""
    return await api_impl.get_comfort_score(
        room_name=room_name,
        hours=hours,
        start_time=start_time,
        end_time=end_time
    )
```

### 4. main.pyへのルート登録
`src/openapi_server/main.py`に追加:
```python
from openapi_server.apis import comfort_api

# 既存のルーター登録に追加
app.include_router(comfort_api.router)
```

### 5. テストの作成
`tests/test_comfort_api.py`:
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from openapi_server.impl.comfort_api_impl import ComfortApiImpl

@pytest.mark.asyncio
async def test_calculate_discomfort_index():
    api = ComfortApiImpl()
    
    # 温度25度、湿度60%の場合
    di = api.calculate_discomfort_index(25.0, 60.0)
    assert 74 < di < 76  # 約75（やや不快）
    
    # 湿度なしの場合
    di = api.calculate_discomfort_index(25.0, None)
    assert di is None

@pytest.mark.asyncio
async def test_di_to_comfort_score():
    api = ComfortApiImpl()
    
    assert api.di_to_comfort_score(50) == 100  # 非常に快適
    assert api.di_to_comfort_score(70) == 50   # 普通
    assert api.di_to_comfort_score(90) == 0    # 非常に不快
    assert api.di_to_comfort_score(None) == 50 # デフォルト

@pytest.mark.asyncio
async def test_get_comfort_score():
    api = ComfortApiImpl()
    
    # モックデータ
    mock_records = [
        {
            "timestamp": datetime.now() - timedelta(hours=1),
            "temperature": 22.5,
            "humidity": 50.0
        },
        {
            "timestamp": datetime.now() - timedelta(hours=2),
            "temperature": 24.0,
            "humidity": 55.0
        }
    ]
    
    with patch.object(api.db_accessor, 'fetch_records', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_records
        
        response = await api.get_comfort_score("living_room", hours=24)
        
        assert response.room_name == "living_room"
        assert len(response.data_points) == 2
        assert response.average_score > 0
        assert response.comfort_level in ["快適", "やや不快", "不快", "非常に不快"]
```

### 6. 動作確認
```bash
# サーバー起動
cd output
uvicorn src.openapi_server.main:app --reload

# 別ターミナルでテスト
curl http://localhost:8000/api/comfort-score/living_room?hours=24

# Swagger UIで確認
open http://localhost:8000/docs
```

### 7. テーブルへのサンプルデータ投入
```sql
-- サンプルデータ
INSERT INTO room_temperature (timestamp, room_name, temperature, humidity) VALUES
(NOW() - INTERVAL '1 hour', 'living_room', 22.5, 50.0),
(NOW() - INTERVAL '2 hours', 'living_room', 23.0, 52.0),
(NOW() - INTERVAL '3 hours', 'living_room', 24.5, 58.0),
(NOW() - INTERVAL '4 hours', 'living_room', 26.0, 65.0),
(NOW() - INTERVAL '5 hours', 'living_room', 27.5, 70.0);
```

## コミットとプルリクエスト
```bash
# テスト実行
pytest tests/test_comfort_api.py

# コミット
git add .
git commit -m "feat: 快適度スコアAPIを実装

- 不快指数計算機能を追加
- 時間帯別の快適度スコアリング
- DatabaseAccessorを使用したデータ取得"

# プッシュとPR作成
git push origin feature/api-comfort-score
```

## 学習ポイント
1. **FastAPIの基本**
   - パスパラメータとクエリパラメータの使い方
   - Pydanticモデルでのレスポンス定義
   - 非同期関数の実装

2. **DatabaseAccessor活用**
   - `fetch_records`の基本的な使い方
   - フィルタリングと並び替え

3. **ビジネスロジック**
   - 不快指数の計算式実装
   - スコアリングロジックの設計

## 注意事項
- 現在のDatabaseAccessorでは日時範囲のフィルタリングがSQLレベルでできないため、Python側で処理しています
- パフォーマンスを考慮する場合は、DatabaseAccessorの拡張が必要です