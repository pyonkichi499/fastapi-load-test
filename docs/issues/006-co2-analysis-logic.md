# Issue #6: CO2分析ロジック実装

## 📋 概要
CO2データから空気質を評価し、換気タイミングを判断するビジネスロジックを実装する

## 🎯 目標
- CO2濃度レベルの判定
- トレンド分析ロジック
- 換気推奨アルゴリズム
- メッセージ生成システム

## 📝 詳細要件

### 実装するクラス
```python
class CO2AnalysisEngine:
    def __init__(self):
        self.GOOD_THRESHOLD = 800      # 良好
        self.CAUTION_THRESHOLD = 1200  # 注意
        # 1200ppm以上は危険
    
    async def analyze_air_quality(
        self, 
        hours: int = 3,
        include_timeline: bool = True
    ) -> AirQualityResult:
        """総合的な空気質分析"""
    
    def determine_status(self, current_co2: int, analysis: Dict) -> str:
        """状態判定ロジック"""
    
    def calculate_trend(self, readings: List[Dict]) -> Dict[str, Any]:
        """トレンド計算"""
    
    def generate_recommendations(self, status: str, analysis: Dict) -> List[str]:
        """推奨アクション生成"""
    
    def generate_message(self, status: str, analysis: Dict) -> str:
        """メッセージ生成"""
```

### 状態判定ロジック（優先順位）

#### 1. 危険レベル判定
```python
def is_danger_level(self, current_co2: int, analysis: Dict) -> bool:
    """危険レベルの判定"""
    
    # 1. 現在値が1200ppm以上
    if current_co2 >= self.CAUTION_THRESHOLD:
        return True
    
    # 2. 高CO2状態が2時間以上継続
    if analysis.get('high_co2_duration_minutes', 0) >= 120:
        return True
    
    # 3. 急激な上昇（30分で300ppm以上）
    if analysis.get('co2_change_30min', 0) >= 300:
        return True
    
    return False
```

#### 2. 注意レベル判定
```python
def is_caution_level(self, current_co2: int, analysis: Dict) -> bool:
    """注意レベルの判定"""
    
    # 1. 現在値が800-1199ppm
    if self.GOOD_THRESHOLD <= current_co2 < self.CAUTION_THRESHOLD:
        return True
    
    # 2. 上昇傾向（1時間で200ppm以上上昇）
    if analysis.get('co2_change_1h', 0) >= 200:
        return True
    
    # 3. 高CO2状態が30分以上継続
    if analysis.get('high_co2_duration_minutes', 0) >= 30:
        return True
    
    return False
```

### トレンド分析

#### 1. 基本トレンド計算
```python
def calculate_basic_trend(self, readings: List[Dict]) -> Dict[str, Any]:
    """基本的なトレンド分析"""
    
    if len(readings) < 60:  # 最低1時間分のデータが必要
        return {"trend": "insufficient_data"}
    
    # 直近1時間と前1時間の平均を比較
    recent_hour = readings[-60:]  # 直近1時間
    previous_hour = readings[-120:-60]  # 前1時間
    
    recent_avg = sum(r['co2'] for r in recent_hour) / len(recent_hour)
    previous_avg = sum(r['co2'] for r in previous_hour) / len(previous_hour)
    
    difference = recent_avg - previous_avg
    
    # トレンド判定
    if difference > 100:
        trend = "急上昇"
    elif difference > 50:
        trend = "上昇傾向"
    elif difference < -100:
        trend = "急下降"
    elif difference < -50:
        trend = "下降傾向"
    else:
        trend = "安定"
    
    return {
        "trend": trend,
        "recent_avg": recent_avg,
        "previous_avg": previous_avg,
        "change_amount": difference,
        "change_rate": (difference / previous_avg * 100) if previous_avg > 0 else 0
    }
```

#### 2. 高度なトレンド分析
```python
def calculate_advanced_trend(self, readings: List[Dict]) -> Dict[str, Any]:
    """線形回帰によるトレンド分析"""
    
    import numpy as np
    from scipy import stats
    
    if len(readings) < 30:
        return self.calculate_basic_trend(readings)
    
    # 時系列データの準備
    timestamps = [r['datetime'].timestamp() for r in readings]
    co2_values = [r['co2'] for r in readings]
    
    # 線形回帰
    slope, intercept, r_value, p_value, std_err = stats.linregress(timestamps, co2_values)
    
    # 30分後の予測値
    future_time = timestamps[-1] + 1800  # 30分後
    predicted_co2 = slope * future_time + intercept
    
    # トレンドの信頼性
    confidence = abs(r_value)  # 相関係数の絶対値
    
    return {
        "trend_slope": slope * 3600,  # 1時間あたりの変化量
        "predicted_co2_30min": max(0, predicted_co2),
        "trend_confidence": confidence,
        "trend_description": self._describe_trend(slope * 3600, confidence)
    }

def _describe_trend(self, hourly_slope: float, confidence: float) -> str:
    """トレンドの説明文生成"""
    
    if confidence < 0.3:
        return "変動が不規則"
    
    if hourly_slope > 100:
        return "急激に上昇中"
    elif hourly_slope > 30:
        return "上昇傾向"
    elif hourly_slope < -100:
        return "急激に減少中"
    elif hourly_slope < -30:
        return "減少傾向"
    else:
        return "安定している"
```

### 高CO2継続時間の計算
```python
def calculate_high_co2_duration(self, readings: List[Dict]) -> int:
    """高CO2状態の継続時間を計算（分単位）"""
    
    if not readings:
        return 0
    
    # 最新から逆順に確認
    duration_minutes = 0
    for reading in reversed(readings):
        if reading['co2'] >= self.GOOD_THRESHOLD:
            duration_minutes += 1
        else:
            break  # 連続性が途切れたら終了
    
    return duration_minutes
```

### メッセージ生成システム

#### 1. 状態別メッセージ
```python
def generate_status_message(self, status: str, analysis: Dict) -> str:
    """状態に応じたメッセージ生成"""
    
    current_co2 = analysis.get('current_co2', 0)
    trend = analysis.get('trend', 'unknown')
    duration = analysis.get('high_co2_duration_minutes', 0)
    
    if status == "危険":
        if current_co2 >= 1500:
            return f"CO2濃度が非常に高い状態です（{current_co2}ppm）。直ちに換気してください。"
        elif duration >= 120:
            return f"高CO2状態が{duration}分継続しています。速やかに換気が必要です。"
        else:
            return f"CO2濃度が危険レベルです（{current_co2}ppm）。換気してください。"
    
    elif status == "注意":
        if "上昇" in trend:
            return f"CO2濃度が{trend}です（{current_co2}ppm）。そろそろ換気を検討してください。"
        elif duration >= 30:
            return f"やや高いCO2レベルが{duration}分続いています。換気をお勧めします。"
        else:
            return f"CO2濃度がやや高めです（{current_co2}ppm）。換気を検討してください。"
    
    else:  # 良好
        if "下降" in trend:
            return f"CO2濃度が改善されています（{current_co2}ppm）。良好な状態です。"
        else:
            return f"CO2濃度は良好なレベルです（{current_co2}ppm）。"
```

#### 2. 推奨アクション生成
```python
def generate_recommendations(self, status: str, analysis: Dict) -> List[str]:
    """具体的な推奨アクションを生成"""
    
    recommendations = []
    current_co2 = analysis.get('current_co2', 0)
    trend = analysis.get('trend', '')
    temperature = analysis.get('current_temperature', 23)
    
    if status == "危険":
        recommendations.extend([
            "🪟 すべての窓を開けて換気してください",
            "⏰ 15分間は換気を続けることをお勧めします",
            "📊 15分後に再度確認してください"
        ])
        
        if temperature < 20:
            recommendations.append("🌡️ 寒い場合は短時間で集中的に換気してください")
    
    elif status == "注意":
        recommendations.extend([
            "🪟 窓を開けて5-10分間換気してください",
            "💨 可能であれば空気清浄機も併用してください"
        ])
        
        if "上昇" in trend:
            recommendations.append("📈 上昇傾向のため早めの対応をお勧めします")
        
        recommendations.append("⏰ 30分後に再度確認してください")
    
    else:  # 良好
        if current_co2 > 600:
            recommendations.append("👍 現在の状態を維持してください")
        else:
            recommendations.append("✨ 空気がとても清浄です")
    
    return recommendations
```

## ✅ 完了条件
- [ ] CO2AnalysisEngineクラスの実装
- [ ] 状態判定ロジックの実装
- [ ] トレンド分析機能
- [ ] メッセージ生成システム
- [ ] 推奨アクション生成
- [ ] 単体テストの作成

## 🧪 テスト内容
```python
async def test_danger_level_detection():
    engine = CO2AnalysisEngine()
    
    # 高CO2値テスト
    assert engine.is_danger_level(1300, {}) == True
    
    # 長時間継続テスト
    assert engine.is_danger_level(900, {'high_co2_duration_minutes': 150}) == True
    
    # 正常値テスト
    assert engine.is_danger_level(700, {}) == False

async def test_trend_calculation():
    # 上昇トレンドのテストデータ
    readings = generate_upward_trend_data()
    engine = CO2AnalysisEngine()
    
    trend = engine.calculate_basic_trend(readings)
    assert "上昇" in trend["trend"]
    assert trend["change_amount"] > 0

async def test_message_generation():
    engine = CO2AnalysisEngine()
    
    # 危険レベルメッセージ
    message = engine.generate_status_message("危険", {
        'current_co2': 1300,
        'trend': '急上昇'
    })
    assert "直ちに" in message or "速やかに" in message

async def test_recommendations():
    engine = CO2AnalysisEngine()
    
    recommendations = engine.generate_recommendations("危険", {
        'current_co2': 1400,
        'current_temperature': 22
    })
    
    assert len(recommendations) >= 3
    assert any("窓" in rec for rec in recommendations)
```

## 📁 ファイル構成
```
src/analysis/
├── __init__.py
├── co2_analysis_engine.py   # 新規作成
├── trend_analyzer.py        # 新規作成
└── message_generator.py     # 新規作成
tests/
└── test_co2_analysis.py     # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #5 BigQuery専用クエリ実装
- 次のIssue: #7 Pydanticモデル定義

## 🎯 分析の特徴
- **多段階判定**: 複数の条件を組み合わせた堅牢な判定
- **トレンド重視**: 単発値ではなく変化傾向を重視
- **実用的メッセージ**: 具体的で実行可能なアドバイス
- **パーソナライズ**: 温度などの環境要因も考慮