# 成長曲線API実装手順

## 概要
ルービックキューブのソルブタイムの履歴から、プレイヤーの成長曲線を可視化し、今後の成長予測を提供するAPIです。

## ブランチ作成
```bash
git checkout develop
git pull origin develop
git checkout -b feature/api-cube-progress
```

## 実装手順

### 1. レスポンスモデルの作成
`src/openapi_server/models/cube_progress.py`:
```python
from pydantic import BaseModel
from datetime import datetime
from typing import List, Optional

class ProgressDataPoint(BaseModel):
    timestamp: datetime
    solve_time_ms: int
    solve_time_seconds: float  # ms を秒に変換
    moving_average: Optional[float]  # 移動平均（5回分）

class ProgressStats(BaseModel):
    total_solves: int
    first_solve_time: float
    current_average: float
    best_time: float
    worst_time: float
    improvement_rate: float  # 初回からの改善率（%）
    consistency_score: float  # 標準偏差から計算した安定性スコア（0-100）

class ProgressPrediction(BaseModel):
    predicted_sub10_date: Optional[datetime]  # 10秒切り予測日
    predicted_sub10_probability: float  # 10秒切り達成確率（%）
    next_milestone: str  # 次の目標（例: "Sub-15", "Sub-10"）
    solves_to_milestone: Optional[int]  # 目標達成までの推定回数

class CubeProgressResponse(BaseModel):
    player_name: str
    data_points: List[ProgressDataPoint]
    stats: ProgressStats
    prediction: ProgressPrediction
    message: str  # 励ましのメッセージ
```

### 2. API実装クラスの作成
`src/openapi_server/impl/cube_progress_api_impl.py`:
```python
from datetime import datetime, timedelta
from typing import List, Optional
import statistics
from fastapi import HTTPException

from openapi_server.apis.cube_progress_api_base import BaseCubeProgressApi
from database.accessor import DatabaseAccessor
from database.config import get_db_settings
from openapi_server.models.cube_progress import (
    CubeProgressResponse, ProgressDataPoint, ProgressStats, ProgressPrediction
)

class CubeProgressApiImpl(BaseCubeProgressApi):
    def __init__(self):
        self.settings = get_db_settings()
        self.db_accessor = DatabaseAccessor(self.settings)
    
    def calculate_moving_average(self, times: List[float], window: int = 5) -> List[Optional[float]]:
        """移動平均を計算"""
        averages = []
        for i in range(len(times)):
            if i < window - 1:
                averages.append(None)
            else:
                window_times = times[i - window + 1:i + 1]
                averages.append(sum(window_times) / len(window_times))
        return averages
    
    def calculate_consistency_score(self, times: List[float]) -> float:
        """安定性スコアを計算（標準偏差ベース）"""
        if len(times) < 2:
            return 50.0
        
        std_dev = statistics.stdev(times)
        mean = statistics.mean(times)
        cv = (std_dev / mean) * 100  # 変動係数
        
        # CV: 5%以下=100点, 30%以上=0点
        if cv <= 5:
            return 100.0
        elif cv >= 30:
            return 0.0
        else:
            return 100.0 - (cv - 5) * 4  # 線形補間
    
    def predict_milestone(self, times: List[float], timestamps: List[datetime]) -> ProgressPrediction:
        """マイルストーン達成予測"""
        if len(times) < 10:
            return ProgressPrediction(
                predicted_sub10_date=None,
                predicted_sub10_probability=0.0,
                next_milestone="More data needed",
                solves_to_milestone=None
            )
        
        # 最近の平均タイム
        recent_avg = statistics.mean(times[-20:]) if len(times) >= 20 else statistics.mean(times)
        
        # 改善率の計算（最近20回）
        if len(times) >= 20:
            old_avg = statistics.mean(times[-40:-20]) if len(times) >= 40 else statistics.mean(times[:10])
            improvement_per_solve = (old_avg - recent_avg) / 20
        else:
            improvement_per_solve = (times[0] - times[-1]) / len(times)
        
        # 次のマイルストーンを決定
        milestones = [30, 25, 20, 15, 12, 10, 8, 7, 6, 5]
        next_milestone = None
        for ms in milestones:
            if recent_avg > ms:
                next_milestone = ms
                break
        
        if next_milestone is None:
            next_milestone_str = "World Class!"
            solves_to_milestone = None
        else:
            next_milestone_str = f"Sub-{next_milestone}"
            # 目標達成までの推定回数
            if improvement_per_solve > 0:
                solves_to_milestone = int((recent_avg - next_milestone) / improvement_per_solve)
            else:
                solves_to_milestone = None
        
        # 10秒切り予測
        if recent_avg > 10:
            if improvement_per_solve > 0:
                solves_to_sub10 = int((recent_avg - 10) / improvement_per_solve)
                days_per_solve = (timestamps[-1] - timestamps[0]).days / len(timestamps)
                predicted_date = datetime.now() + timedelta(days=solves_to_sub10 * days_per_solve)
                
                # 確率計算（簡易版）
                if recent_avg < 12:
                    probability = 80.0
                elif recent_avg < 15:
                    probability = 50.0
                else:
                    probability = 20.0
            else:
                predicted_date = None
                probability = 10.0
        else:
            predicted_date = None
            probability = 100.0
        
        return ProgressPrediction(
            predicted_sub10_date=predicted_date,
            predicted_sub10_probability=probability,
            next_milestone=next_milestone_str,
            solves_to_milestone=solves_to_milestone
        )
    
    def generate_message(self, stats: ProgressStats, prediction: ProgressPrediction) -> str:
        """励ましのメッセージを生成"""
        if stats.improvement_rate > 50:
            return "素晴らしい成長率です！この調子で練習を続けましょう！"
        elif stats.improvement_rate > 20:
            return "着実に上達しています。継続は力なり！"
        elif stats.current_average < 10:
            return "Sub-10達成おめでとうございます！次は安定性を高めましょう！"
        elif prediction.predicted_sub10_probability > 70:
            return f"Sub-10まであと少し！{prediction.solves_to_milestone}回程度で達成予測です！"
        else:
            return "毎日の練習が上達への近道です。焦らず楽しみましょう！"
    
    async def get_cube_progress(
        self,
        player_name: str,
        days: Optional[int] = None,
        limit: Optional[int] = None
    ) -> CubeProgressResponse:
        """プレイヤーの成長曲線データを取得"""
        
        # データ取得
        try:
            filters = {"player_name": player_name}
            
            records = await self.db_accessor.fetch_records(
                table_name="cube_times",
                columns=["timestamp", "solve_time_ms"],
                filters=filters,
                order_by=[("timestamp", "ASC")],
                limit=limit
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Database error: {str(e)}")
        
        if not records:
            raise HTTPException(status_code=404, detail=f"No data found for player: {player_name}")
        
        # 期間フィルタリング（必要な場合）
        if days:
            cutoff_date = datetime.now() - timedelta(days=days)
            records = [r for r in records if r["timestamp"] >= cutoff_date]
        
        # データ変換
        timestamps = [r["timestamp"] for r in records]
        times_ms = [r["solve_time_ms"] for r in records]
        times_sec = [ms / 1000.0 for ms in times_ms]
        
        # 移動平均計算
        moving_averages = self.calculate_moving_average(times_sec)
        
        # データポイント作成
        data_points = []
        for i, record in enumerate(records):
            data_points.append(ProgressDataPoint(
                timestamp=record["timestamp"],
                solve_time_ms=record["solve_time_ms"],
                solve_time_seconds=times_sec[i],
                moving_average=moving_averages[i]
            ))
        
        # 統計情報計算
        stats = ProgressStats(
            total_solves=len(records),
            first_solve_time=times_sec[0],
            current_average=statistics.mean(times_sec[-5:]) if len(times_sec) >= 5 else statistics.mean(times_sec),
            best_time=min(times_sec),
            worst_time=max(times_sec),
            improvement_rate=((times_sec[0] - stats.current_average) / times_sec[0]) * 100,
            consistency_score=self.calculate_consistency_score(times_sec[-20:] if len(times_sec) >= 20 else times_sec)
        )
        
        # 予測
        prediction = self.predict_milestone(times_sec, timestamps)
        
        # メッセージ生成
        message = self.generate_message(stats, prediction)
        
        return CubeProgressResponse(
            player_name=player_name,
            data_points=data_points,
            stats=stats,
            prediction=prediction,
            message=message
        )
```

### 3. APIルートの追加
`src/openapi_server/apis/cube_progress_api.py`:
```python
from typing import Optional
from fastapi import APIRouter, Query, Path

from openapi_server.impl.cube_progress_api_impl import CubeProgressApiImpl
from openapi_server.models.cube_progress import CubeProgressResponse

router = APIRouter(prefix="/api/cube", tags=["cube"])
api_impl = CubeProgressApiImpl()

@router.get("/progress/{player_name}", response_model=CubeProgressResponse)
async def get_cube_progress(
    player_name: str = Path(..., description="プレイヤー名"),
    days: Optional[int] = Query(None, description="取得する日数", ge=1, le=365),
    limit: Optional[int] = Query(None, description="取得する最大件数", ge=1, le=1000)
):
    """指定されたプレイヤーの成長曲線データを取得します"""
    return await api_impl.get_cube_progress(
        player_name=player_name,
        days=days,
        limit=limit
    )
```

### 4. main.pyへのルート登録
`src/openapi_server/main.py`に追加:
```python
from openapi_server.apis import cube_progress_api

# 既存のルーター登録に追加
app.include_router(cube_progress_api.router)
```

### 5. テストの作成
`tests/test_cube_progress_api.py`:
```python
import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

from openapi_server.impl.cube_progress_api_impl import CubeProgressApiImpl

@pytest.mark.asyncio
async def test_calculate_moving_average():
    api = CubeProgressApiImpl()
    
    times = [15.2, 14.8, 15.5, 14.2, 13.9, 14.1, 13.5]
    averages = api.calculate_moving_average(times, window=3)
    
    assert averages[0] is None
    assert averages[1] is None
    assert averages[2] == pytest.approx(15.17, 0.01)  # (15.2 + 14.8 + 15.5) / 3

@pytest.mark.asyncio
async def test_calculate_consistency_score():
    api = CubeProgressApiImpl()
    
    # 安定したタイム
    stable_times = [10.1, 10.2, 10.0, 10.3, 10.1]
    score = api.calculate_consistency_score(stable_times)
    assert score > 90  # 高い安定性スコア
    
    # 不安定なタイム
    unstable_times = [10.0, 15.0, 8.0, 20.0, 12.0]
    score = api.calculate_consistency_score(unstable_times)
    assert score < 50  # 低い安定性スコア

@pytest.mark.asyncio
async def test_get_cube_progress():
    api = CubeProgressApiImpl()
    
    # モックデータ（成長を示すデータ）
    mock_records = []
    base_time = datetime.now() - timedelta(days=30)
    
    for i in range(50):
        mock_records.append({
            "timestamp": base_time + timedelta(days=i*0.6),
            "solve_time_ms": 20000 - i * 200  # 20秒から徐々に速くなる
        })
    
    with patch.object(api.db_accessor, 'fetch_records', new_callable=AsyncMock) as mock_fetch:
        mock_fetch.return_value = mock_records
        
        response = await api.get_cube_progress("test_player")
        
        assert response.player_name == "test_player"
        assert len(response.data_points) == 50
        assert response.stats.total_solves == 50
        assert response.stats.improvement_rate > 0
        assert response.prediction.next_milestone is not None
```

### 6. 動作確認
```bash
# サーバー起動
cd output
uvicorn src.openapi_server.main:app --reload

# 別ターミナルでテスト
curl http://localhost:8000/api/cube/progress/player1?days=30

# Swagger UIで確認
open http://localhost:8000/docs
```

### 7. テーブルへのサンプルデータ投入
```sql
-- 成長を示すサンプルデータ（30日分）
DO $$
DECLARE
    i INTEGER;
    base_time TIMESTAMP;
    solve_time INTEGER;
BEGIN
    base_time := NOW() - INTERVAL '30 days';
    
    FOR i IN 0..99 LOOP
        -- 20秒から徐々に速くなる（ランダム性あり）
        solve_time := 20000 - (i * 150) + (RANDOM() * 2000 - 1000)::INTEGER;
        solve_time := GREATEST(solve_time, 8000); -- 最低8秒
        
        INSERT INTO cube_times (timestamp, player_name, solve_time_ms, cube_type)
        VALUES (
            base_time + (i * INTERVAL '7 hours'),
            'sample_player',
            solve_time,
            '3x3'
        );
    END LOOP;
END $$;
```

## コミットとプルリクエスト
```bash
# テスト実行
pytest tests/test_cube_progress_api.py

# コミット
git add .
git commit -m "feat: ルービックキューブ成長曲線APIを実装

- 移動平均による成長トレンド可視化
- 統計情報と安定性スコアの計算
- マイルストーン達成予測機能
- 励ましメッセージ生成"

# プッシュとPR作成
git push origin feature/api-cube-progress
```

## 学習ポイント
1. **データ処理**
   - 時系列データの処理
   - 移動平均の計算
   - 統計量の算出

2. **DatabaseAccessor活用**
   - 並び替え（ORDER BY）の使用
   - limit パラメータの活用

3. **ビジネスロジック**
   - 成長予測アルゴリズムの実装
   - パフォーマンス指標の設計

## 拡張アイデア
- グラフ描画用のデータフォーマット追加
- 他プレイヤーとの比較機能
- 練習セッション単位での分析