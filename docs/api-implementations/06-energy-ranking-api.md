# 省エネランキングAPI実装手順

## 概要
部屋ごとの温度管理効率を評価し、快適温度範囲（20-26度）を維持した時間の割合でランキングを作成するAPIです。拡張されたDatabaseAccessorを使用します。

## 前提条件
- `feature/db-enhancement`ブランチの機能が必要
- EnhancedDatabaseAccessorが実装済み

## ブランチ作成
```bash
git checkout develop
git pull origin develop
# feature/db-enhancementがマージ済みであることを確認
git checkout -b feature/api-energy-ranking
```

## 実装手順

### 1. レスポンスモデルの作成
`src/openapi_server/models/energy_ranking.py`:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class RoomEfficiencyData(BaseModel):
    room_name: str
    total_records: int
    comfort_records: int  # 快適範囲内の記録数
    efficiency_rate: float  # 効率率（%）
    average_temperature: float
    temperature_variance: float  # 温度のばらつき
    comfort_score: int  # 総合快適スコア（0-100）
    grade: str  # "A+", "A", "B", "C", "D"

class EfficiencyTrend(BaseModel):
    date: datetime
    efficiency_rate: float
    average_temperature: float

class SeasonalComparison(BaseModel):
    current_period: str  # "今月", "今週"
    previous_period: str  # "先月", "先週"
    efficiency_change: float  # 変化率（%）
    improvement_direction: str  # "向上", "悪化", "変化なし"

class EnergyTips(BaseModel):
    tip_category: str  # "冷房", "暖房", "換気", "全般"
    message: str
    expected_improvement: float  # 期待される改善率（%）

class EnergyRankingResponse(BaseModel):
    ranking_period: str  # "過去30日間"
    generated_at: datetime
    room_rankings: List[RoomEfficiencyData]
    efficiency_trends: List[EfficiencyTrend]  # 過去7日間の推移
    seasonal_comparison: Optional[SeasonalComparison]
    champion_room: Optional[str]  # 月間チャンピオン
    energy_tips: List[EnergyTips]
    total_rooms: int
    average_efficiency: float
```

### 2. API実装クラスの作成
`src/openapi_server/impl/energy_ranking_api_impl.py`:
```python
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
import statistics
from fastapi import HTTPException

from openapi_server.apis.energy_ranking_api_base import BaseEnergyRankingApi
from database.enhanced_accessor import EnhancedDatabaseAccessor
from database.config import get_db_settings
from openapi_server.models.energy_ranking import (
    EnergyRankingResponse, RoomEfficiencyData, EfficiencyTrend,
    SeasonalComparison, EnergyTips
)

class EnergyRankingApiImpl(BaseEnergyRankingApi):
    def __init__(self):
        self.settings = get_db_settings()
        self.db_accessor = EnhancedDatabaseAccessor(self.settings)
        
        # 快適温度範囲の設定
        self.COMFORT_TEMP_MIN = 20.0
        self.COMFORT_TEMP_MAX = 26.0
    
    def calculate_comfort_score(
        self, 
        efficiency_rate: float,
        avg_temp: float,
        variance: float
    ) -> int:
        """総合快適スコアを計算"""
        
        # 1. 効率率スコア（60%の重み）
        efficiency_score = efficiency_rate  # 既に0-100の値
        
        # 2. 理想温度からの距離スコア（25%の重み）
        ideal_temp = 23.0  # 理想温度
        temp_diff = abs(avg_temp - ideal_temp)
        temp_score = max(0, 100 - (temp_diff * 20))  # 1度差で20点減点
        
        # 3. 安定性スコア（15%の重み）
        stability_score = max(0, 100 - (variance * 30))  # 分散1で30点減点
        
        # 重み付き平均
        total_score = (\n            efficiency_score * 0.6 +\n            temp_score * 0.25 +\n            stability_score * 0.15\n        )
        
        return int(max(0, min(100, total_score)))
    
    def assign_grade(self, comfort_score: int) -> str:
        """スコアに基づいてグレードを決定"""
        if comfort_score >= 90:
            return \"A+\"
        elif comfort_score >= 80:
            return \"A\"
        elif comfort_score >= 70:
            return \"B\"
        elif comfort_score >= 60:
            return \"C\"
        else:
            return \"D\"
    
    def generate_energy_tips(self, room_data: List[RoomEfficiencyData]) -> List[EnergyTips]:
        \"\"\"効率改善のためのアドバイスを生成\"\"\"
        tips = []
        
        # 全体の平均効率を計算
        avg_efficiency = statistics.mean([r.efficiency_rate for r in room_data])
        
        if avg_efficiency < 50:
            tips.append(EnergyTips(
                tip_category=\"全般\",
                message=\"全体的に効率が低めです。設定温度を22-24度に調整することをお勧めします\",
                expected_improvement=15.0
            ))
        
        # 低効率の部屋に特化したアドバイス
        low_efficiency_rooms = [r for r in room_data if r.efficiency_rate < 60]
        if low_efficiency_rooms:
            tips.append(EnergyTips(
                tip_category=\"冷房\",
                message=f\"{', '.join([r.room_name for r in low_efficiency_rooms[:3]])}の冷房設定を見直してみてください\",
                expected_improvement=20.0
            ))
        
        # 温度ばらつきが大きい部屋
        unstable_rooms = [r for r in room_data if r.temperature_variance > 2.0]
        if unstable_rooms:
            tips.append(EnergyTips(
                tip_category=\"換気\",
                message=\"温度のばらつきが大きい部屋では、換気を改善すると安定します\",
                expected_improvement=10.0
            ))
        
        # 高効率の部屋からの学習
        high_efficiency_rooms = [r for r in room_data if r.efficiency_rate > 80]
        if high_efficiency_rooms:
            best_room = max(high_efficiency_rooms, key=lambda x: x.efficiency_rate)
            tips.append(EnergyTips(
                tip_category=\"全般\",
                message=f\"{best_room.room_name}の設定を他の部屋でも参考にしてみてください\",
                expected_improvement=12.0
            ))
        
        return tips
    
    async def get_efficiency_trends(self, days: int = 7) -> List[EfficiencyTrend]:
        \"\"\"過去N日間の効率推移を取得\"\"\"
        
        # 日別の効率データを取得
        end_date = datetime.now().replace(hour=23, minute=59, second=59)
        start_date = end_date - timedelta(days=days-1)
        
        # PostgreSQL用のクエリ（DATE関数使用）
        query = '''
            SELECT 
                DATE(timestamp) as date,
                COUNT(*) as total_count,
                SUM(CASE WHEN temperature BETWEEN :min_temp AND :max_temp THEN 1 ELSE 0 END) as comfort_count,
                AVG(temperature) as avg_temp
            FROM room_temperature
            WHERE timestamp >= :start_date AND timestamp <= :end_date
            GROUP BY DATE(timestamp)
            ORDER BY date ASC
        '''
        
        try:
            results = await self.db_accessor.execute_raw_query(
                query_string=query,
                params={
                    \"start_date\": start_date,
                    \"end_date\": end_date,
                    \"min_temp\": self.COMFORT_TEMP_MIN,
                    \"max_temp\": self.COMFORT_TEMP_MAX
                }
            )
        except Exception as e:
            # SQLiteの場合はfallback
            query_sqlite = '''
                SELECT 
                    strftime('%Y-%m-%d', timestamp) as date,
                    COUNT(*) as total_count,
                    SUM(CASE WHEN temperature BETWEEN :min_temp AND :max_temp THEN 1 ELSE 0 END) as comfort_count,
                    AVG(temperature) as avg_temp
                FROM room_temperature
                WHERE timestamp >= :start_date AND timestamp <= :end_date
                GROUP BY strftime('%Y-%m-%d', timestamp)
                ORDER BY date ASC
            '''
            
            results = await self.db_accessor.execute_raw_query(
                query_string=query_sqlite,
                params={
                    \"start_date\": start_date,
                    \"end_date\": end_date,
                    \"min_temp\": self.COMFORT_TEMP_MIN,
                    \"max_temp\": self.COMFORT_TEMP_MAX
                }
            )
        
        trends = []
        for result in results:
            efficiency_rate = (result[\"comfort_count\"] / result[\"total_count\"]) * 100 if result[\"total_count\"] > 0 else 0
            
            # 日付の変換
            if isinstance(result[\"date\"], str):
                date_obj = datetime.strptime(result[\"date\"], \"%Y-%m-%d\")
            else:
                date_obj = result[\"date\"]
            
            trends.append(EfficiencyTrend(
                date=date_obj,
                efficiency_rate=efficiency_rate,
                average_temperature=float(result[\"avg_temp\"])
            ))
        
        return trends
    
    async def get_seasonal_comparison(self) -> Optional[SeasonalComparison]:
        \"\"\"月間比較データを取得\"\"\"
        
        # 今月と先月のデータを比較
        now = datetime.now()
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        previous_month_start = (current_month_start - timedelta(days=1)).replace(day=1)
        previous_month_end = current_month_start - timedelta(seconds=1)
        
        # 今月のデータ
        current_data = await self.db_accessor.fetch_aggregated_records(
            table_name=\"room_temperature\",
            group_by=[],  # 全体の集計
            aggregations={
                \"total_count\": {\"function\": \"COUNT\", \"column\": \"*\"},
                \"comfort_count\": {
                    \"function\": \"SUM\", 
                    \"column\": \"CASE WHEN temperature BETWEEN 20 AND 26 THEN 1 ELSE 0 END\"
                }
            },
            filters={}  # 日付フィルタは生クエリで対応
        )
        
        # より簡単な方法：生クエリで直接取得
        current_query = '''
            SELECT 
                COUNT(*) as total_count,
                SUM(CASE WHEN temperature BETWEEN :min_temp AND :max_temp THEN 1 ELSE 0 END) as comfort_count
            FROM room_temperature
            WHERE timestamp >= :start_date
        '''
        
        previous_query = '''
            SELECT 
                COUNT(*) as total_count,
                SUM(CASE WHEN temperature BETWEEN :min_temp AND :max_temp THEN 1 ELSE 0 END) as comfort_count
            FROM room_temperature
            WHERE timestamp >= :start_date AND timestamp <= :end_date
        '''
        
        try:
            current_result = await self.db_accessor.execute_raw_query(
                current_query,
                {
                    \"start_date\": current_month_start,
                    \"min_temp\": self.COMFORT_TEMP_MIN,
                    \"max_temp\": self.COMFORT_TEMP_MAX
                }
            )
            
            previous_result = await self.db_accessor.execute_raw_query(
                previous_query,
                {
                    \"start_date\": previous_month_start,
                    \"end_date\": previous_month_end,
                    \"min_temp\": self.COMFORT_TEMP_MIN,
                    \"max_temp\": self.COMFORT_TEMP_MAX
                }
            )
            
            if current_result and previous_result:
                current_efficiency = (current_result[0][\"comfort_count\"] / current_result[0][\"total_count\"]) * 100 if current_result[0][\"total_count\"] > 0 else 0
                previous_efficiency = (previous_result[0][\"comfort_count\"] / previous_result[0][\"total_count\"]) * 100 if previous_result[0][\"total_count\"] > 0 else 0
                
                efficiency_change = current_efficiency - previous_efficiency
                
                if abs(efficiency_change) < 1:
                    direction = \"変化なし\"
                elif efficiency_change > 0:
                    direction = \"向上\"
                else:
                    direction = \"悪化\"
                
                return SeasonalComparison(
                    current_period=\"今月\",
                    previous_period=\"先月\",
                    efficiency_change=efficiency_change,
                    improvement_direction=direction
                )
        except Exception:
            # データが不足している場合
            pass
        
        return None
    
    async def get_energy_ranking(
        self,
        days: int = 30,
        include_trends: bool = True
    ) -> EnergyRankingResponse:
        \"\"\"省エネランキングを取得\"\"\"
        
        # 期間の設定
        end_time = datetime.now()
        start_time = end_time - timedelta(days=days)
        
        # 部屋ごとの効率データを取得
        try:
            room_efficiency_data = await self.db_accessor.fetch_aggregated_records(
                table_name=\"room_temperature\",
                group_by=[\"room_name\"],
                aggregations={
                    \"total_records\": {\"function\": \"COUNT\", \"column\": \"*\"},
                    \"avg_temperature\": {\"function\": \"AVG\", \"column\": \"temperature\"},
                    \"temp_variance\": {\"function\": \"AVG\", \"column\": \"temperature * temperature\"}  # 分散の近似
                },
                order_by=[(\"total_records\", \"DESC\")]
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f\"Database error: {str(e)}\")
        
        if not room_efficiency_data:
            raise HTTPException(status_code=404, detail=\"No temperature data found\")
        
        # 快適度記録数を別途取得（CASE WHEN がうまく動作しない場合の対応）
        room_rankings = []
        
        for room_data in room_efficiency_data:
            room_name = room_data[\"room_name\"]
            
            # 各部屋の快適範囲内記録数を個別に取得
            comfort_query = '''
                SELECT COUNT(*) as comfort_count
                FROM room_temperature
                WHERE room_name = :room_name 
                  AND temperature BETWEEN :min_temp AND :max_temp
                  AND timestamp >= :start_date
            '''
            
            try:
                comfort_result = await self.db_accessor.execute_raw_query(
                    comfort_query,
                    {
                        \"room_name\": room_name,
                        \"min_temp\": self.COMFORT_TEMP_MIN,
                        \"max_temp\": self.COMFORT_TEMP_MAX,
                        \"start_date\": start_time
                    }
                )
                
                comfort_records = comfort_result[0][\"comfort_count\"] if comfort_result else 0
            except Exception:
                comfort_records = 0
            
            total_records = room_data[\"total_records\"]
            efficiency_rate = (comfort_records / total_records) * 100 if total_records > 0 else 0
            
            # 温度分散の計算（簡易版）
            avg_temp = room_data[\"avg_temperature\"]
            variance_approx = abs(room_data[\"temp_variance\"] - (avg_temp * avg_temp))
            
            # 快適スコアとグレードの計算
            comfort_score = self.calculate_comfort_score(efficiency_rate, avg_temp, variance_approx)
            grade = self.assign_grade(comfort_score)
            
            room_rankings.append(RoomEfficiencyData(
                room_name=room_name,
                total_records=total_records,
                comfort_records=comfort_records,
                efficiency_rate=efficiency_rate,
                average_temperature=avg_temp,
                temperature_variance=variance_approx,
                comfort_score=comfort_score,
                grade=grade
            ))
        
        # ランキング順にソート
        room_rankings.sort(key=lambda x: x.efficiency_rate, reverse=True)
        
        # 効率推移の取得
        efficiency_trends = []
        if include_trends:
            efficiency_trends = await self.get_efficiency_trends(7)
        
        # 季節比較の取得
        seasonal_comparison = await self.get_seasonal_comparison()
        
        # チャンピオン決定
        champion_room = room_rankings[0].room_name if room_rankings else None
        
        # エネルギーのコツ生成
        energy_tips = self.generate_energy_tips(room_rankings)
        
        # 全体統計
        total_rooms = len(room_rankings)
        average_efficiency = statistics.mean([r.efficiency_rate for r in room_rankings]) if room_rankings else 0
        
        return EnergyRankingResponse(
            ranking_period=f\"過去{days}日間\",
            generated_at=datetime.now(),
            room_rankings=room_rankings,
            efficiency_trends=efficiency_trends,
            seasonal_comparison=seasonal_comparison,
            champion_room=champion_room,
            energy_tips=energy_tips,
            total_rooms=total_rooms,
            average_efficiency=average_efficiency
        )
```

### 3. APIルートの追加
`src/openapi_server/apis/energy_ranking_api.py`:
```python
from fastapi import APIRouter, Query

from openapi_server.impl.energy_ranking_api_impl import EnergyRankingApiImpl
from openapi_server.models.energy_ranking import EnergyRankingResponse

router = APIRouter(prefix="/api/energy-saving", tags=["energy"])
api_impl = EnergyRankingApiImpl()

@router.get("/ranking", response_model=EnergyRankingResponse)
async def get_energy_ranking(
    days: int = Query(30, description="ランキング対象期間（日数）", ge=1, le=365),
    include_trends: bool = Query(True, description="効率推移を含めるか")
):
    """省エネ効率ランキングを取得します"""
    return await api_impl.get_energy_ranking(
        days=days,
        include_trends=include_trends
    )
```

### 4. main.pyへのルート登録
`src/openapi_server/main.py`に追加:
```python
from openapi_server.apis import energy_ranking_api

# 既存のルーター登録に追加
app.include_router(energy_ranking_api.router)
```

### 5. テストの作成
`tests/test_energy_ranking_api.py`:
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from openapi_server.impl.energy_ranking_api_impl import EnergyRankingApiImpl

@pytest.mark.asyncio
async def test_calculate_comfort_score():
    api = EnergyRankingApiImpl()
    
    # 高効率、理想温度、低分散
    score = api.calculate_comfort_score(90.0, 23.0, 0.5)
    assert score > 85
    
    # 低効率、極端な温度、高分散
    score = api.calculate_comfort_score(30.0, 30.0, 3.0)
    assert score < 50

@pytest.mark.asyncio
async def test_assign_grade():
    api = EnergyRankingApiImpl()
    
    assert api.assign_grade(95) == "A+"
    assert api.assign_grade(85) == "A"
    assert api.assign_grade(75) == "B"
    assert api.assign_grade(65) == "C"
    assert api.assign_grade(45) == "D"

@pytest.mark.asyncio
async def test_get_energy_ranking():
    api = EnergyRankingApiImpl()
    
    # モック：部屋別統計データ
    mock_room_data = [
        {
            "room_name": "living_room",
            "total_records": 100,
            "avg_temperature": 23.5,
            "temp_variance": 529.0  # 23^2 + variance
        },
        {
            "room_name": "bedroom",
            "total_records": 80,
            "avg_temperature": 25.0,
            "temp_variance": 630.0
        }
    ]
    
    # モック：快適記録数
    mock_comfort_data = [
        [{"comfort_count": 80}],  # living_room
        [{"comfort_count": 60}]   # bedroom
    ]
    
    with patch.object(api.db_accessor, 'fetch_aggregated_records', new_callable=AsyncMock) as mock_agg, \
         patch.object(api.db_accessor, 'execute_raw_query', new_callable=AsyncMock) as mock_raw:
        
        mock_agg.return_value = mock_room_data
        mock_raw.side_effect = mock_comfort_data
        
        response = await api.get_energy_ranking(days=30, include_trends=False)
        
        assert len(response.room_rankings) == 2
        assert response.room_rankings[0].room_name == "living_room"  # 効率が高い順
        assert response.room_rankings[0].efficiency_rate == 80.0
        assert response.champion_room == "living_room"
        assert response.total_rooms == 2
        assert len(response.energy_tips) > 0
```

### 6. 動作確認
```bash
# サーバー起動
cd output
uvicorn src.openapi_server.main:app --reload

# 別ターミナルでテスト
curl http://localhost:8000/api/energy-saving/ranking?days=30

# Swagger UIで確認
open http://localhost:8000/docs
```

## コミットとプルリクエスト
```bash
# テスト実行
pytest tests/test_energy_ranking_api.py -v

# コミット
git add .
git commit -m "feat: 省エネランキングAPIを実装

- 部屋ごとの温度管理効率評価
- EnhancedDatabaseAccessorの集計機能を活用
- 効率推移、季節比較、改善アドバイス機能
- 総合快適スコアとグレード評価システム"

# プッシュとPR作成
git push origin feature/api-energy-ranking
```

## 学習ポイント
1. **高度なデータベース操作**
   - GROUP BY句の実践的な使用
   - 複雑な集計クエリの構築
   - 生SQLとORM機能の使い分け

2. **ビジネスロジック設計**
   - 多要素評価システム
   - ランキングアルゴリズム
   - データドリブンなアドバイス生成

3. **パフォーマンス考慮**
   - 効率的なクエリ設計
   - データ量に応じた処理方法

## 拡張アイデア
- 時間帯別効率分析
- 外気温との相関分析
- 電力消費量との連携
- AIによる最適化提案