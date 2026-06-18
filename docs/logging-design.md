# CO2モニタリングAPI ログ設計

## 📋 概要
CO2モニタリングAPIの包括的なログ設計により、運用監視、デバッグ、ビジネス分析を支援

## 🎯 ログ設計目標
- **可観測性**: システムの状態と動作を完全に把握
- **トラブルシューティング**: 問題の迅速な特定と解決
- **ビジネス分析**: CO2データとユーザー行動の分析
- **セキュリティ**: アクセスログと異常検知
- **パフォーマンス**: レスポンス時間とリソース使用量の追跡

## 🏗️ ログアーキテクチャ

### 1. ログレベル戦略
```python
# src/logging/log_levels.py
import logging
from enum import Enum

class LogLevel(Enum):
    """ログレベル定義"""
    DEBUG = logging.DEBUG      # 開発・デバッグ用詳細情報
    INFO = logging.INFO        # 一般的な情報（API呼び出し、正常処理）
    WARNING = logging.WARNING  # 警告（データ品質問題、性能劣化）
    ERROR = logging.ERROR      # エラー（例外、失敗）
    CRITICAL = logging.CRITICAL # 重大エラー（システム停止）

class LogCategory(Enum):
    """ログカテゴリ"""
    API = "api"                    # APIアクセスログ
    BUSINESS = "business"          # ビジネスロジックログ
    DATABASE = "database"          # データベースアクセスログ
    SECURITY = "security"          # セキュリティ関連ログ
    PERFORMANCE = "performance"    # パフォーマンスログ
    SYSTEM = "system"              # システム動作ログ
    AUDIT = "audit"                # 監査ログ
```

### 2. 構造化ログ設計
```python
# src/logging/structured_logger.py
import json
import uuid
from datetime import datetime
from typing import Dict, Any, Optional
from contextvars import ContextVar
import structlog

# リクエストコンテキスト
request_id: ContextVar[str] = ContextVar('request_id', default='')
user_context: ContextVar[Dict] = ContextVar('user_context', default={})

class StructuredLogger:
    """構造化ログ出力クラス"""
    
    def __init__(self, name: str, category: LogCategory):
        self.logger = structlog.get_logger(name)
        self.category = category.value
        self.base_fields = {
            "service": "co2-monitoring-api",
            "version": "1.0.0",
            "category": self.category
        }
    
    def _enrich_log(self, **kwargs) -> Dict[str, Any]:
        """ログエンリッチメント"""
        
        enriched = self.base_fields.copy()
        enriched.update({
            "timestamp": datetime.utcnow().isoformat(),
            "request_id": request_id.get(),
            "environment": os.getenv("ENVIRONMENT", "development"),
            **kwargs
        })
        
        # ユーザーコンテキスト追加
        user_ctx = user_context.get()
        if user_ctx:
            enriched["user"] = user_ctx
        
        return enriched
    
    def info(self, message: str, **kwargs):
        """INFO レベルログ"""
        self.logger.info(message, **self._enrich_log(**kwargs))
    
    def warning(self, message: str, **kwargs):
        """WARNING レベルログ"""
        self.logger.warning(message, **self._enrich_log(**kwargs))
    
    def error(self, message: str, error: Exception = None, **kwargs):
        """ERROR レベルログ"""
        enriched = self._enrich_log(**kwargs)
        
        if error:
            enriched.update({
                "error_type": type(error).__name__,
                "error_message": str(error),
                "traceback": traceback.format_exc()
            })
        
        self.logger.error(message, **enriched)
    
    def critical(self, message: str, **kwargs):
        """CRITICAL レベルログ"""
        self.logger.critical(message, **self._enrich_log(**kwargs))

# ログ設定
def configure_structured_logging():
    """構造化ログ設定"""
    
    processors = [
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.dev.ConsoleRenderer() if os.getenv("ENVIRONMENT") == "development" 
                                        else structlog.processors.JSONRenderer()
    ]
    
    structlog.configure(
        processors=processors,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )
```

## 📊 ログカテゴリ別設計

### 1. APIアクセスログ
```python
# src/logging/api_logger.py
class APILogger(StructuredLogger):
    """APIアクセス専用ログ"""
    
    def __init__(self):
        super().__init__("api", LogCategory.API)
    
    def log_request(
        self,
        method: str,
        endpoint: str,
        params: Dict,
        headers: Dict,
        client_ip: str,
        user_agent: str
    ):
        """APIリクエストログ"""
        
        self.info(
            "API request received",
            http_method=method,
            endpoint=endpoint,
            query_params=params,
            client_ip=client_ip,
            user_agent=user_agent,
            content_length=headers.get("content-length", 0)
        )
    
    def log_response(
        self,
        method: str,
        endpoint: str,
        status_code: int,
        response_time_ms: float,
        response_size: int = 0
    ):
        """APIレスポンスログ"""
        
        log_level = "info"
        if status_code >= 500:
            log_level = "error"
        elif status_code >= 400:
            log_level = "warning"
        
        log_data = {
            "http_method": method,
            "endpoint": endpoint,
            "status_code": status_code,
            "response_time_ms": response_time_ms,
            "response_size_bytes": response_size
        }
        
        if log_level == "error":
            self.error("API request failed", **log_data)
        elif log_level == "warning":
            self.warning("API request error", **log_data)
        else:
            self.info("API request completed", **log_data)
    
    def log_rate_limit(self, client_ip: str, endpoint: str, limit: int):
        """レート制限ログ"""
        
        self.warning(
            "Rate limit exceeded",
            client_ip=client_ip,
            endpoint=endpoint,
            rate_limit=limit,
            action="request_rejected"
        )
```

### 2. ビジネスログ
```python
# src/logging/business_logger.py
class BusinessLogger(StructuredLogger):
    """ビジネスロジック専用ログ"""
    
    def __init__(self):
        super().__init__("business", LogCategory.BUSINESS)
    
    def log_air_quality_analysis(
        self,
        room_name: str,
        current_co2: int,
        status: str,
        action: str,
        analysis_duration_ms: float
    ):
        """空気質分析ログ"""
        
        self.info(
            "Air quality analysis completed",
            room_name=room_name,
            current_co2_ppm=current_co2,
            air_quality_status=status,
            recommended_action=action,
            analysis_duration_ms=analysis_duration_ms,
            co2_level_category=self._categorize_co2_level(current_co2)
        )
    
    def log_data_quality_issue(
        self,
        issue_type: str,
        description: str,
        affected_data: Dict,
        severity: str = "medium"
    ):
        """データ品質問題ログ"""
        
        log_method = getattr(self, severity.lower(), self.warning)
        
        log_method(
            "Data quality issue detected",
            issue_type=issue_type,
            description=description,
            affected_data=affected_data,
            severity=severity,
            requires_attention=severity in ["high", "critical"]
        )
    
    def log_threshold_exceeded(
        self,
        threshold_type: str,
        current_value: float,
        threshold_value: float,
        duration_minutes: int
    ):
        """閾値超過ログ"""
        
        self.warning(
            "Threshold exceeded",
            threshold_type=threshold_type,
            current_value=current_value,
            threshold_value=threshold_value,
            duration_minutes=duration_minutes,
            severity=self._calculate_severity(current_value, threshold_value)
        )
    
    def _categorize_co2_level(self, co2_ppm: int) -> str:
        """CO2レベル分類"""
        if co2_ppm < 600:
            return "excellent"
        elif co2_ppm < 800:
            return "good"
        elif co2_ppm < 1200:
            return "acceptable"
        elif co2_ppm < 1500:
            return "poor"
        else:
            return "unacceptable"
    
    def _calculate_severity(self, current: float, threshold: float) -> str:
        """重要度計算"""
        ratio = current / threshold
        if ratio >= 2.0:
            return "critical"
        elif ratio >= 1.5:
            return "high"
        elif ratio >= 1.2:
            return "medium"
        else:
            return "low"
```

### 3. データベースログ
```python
# src/logging/database_logger.py
class DatabaseLogger(StructuredLogger):
    """データベースアクセス専用ログ"""
    
    def __init__(self):
        super().__init__("database", LogCategory.DATABASE)
    
    def log_query_execution(
        self,
        query_type: str,
        table_name: str,
        execution_time_ms: float,
        rows_affected: int,
        query_hash: str = None
    ):
        """クエリ実行ログ"""
        
        log_level = "info"
        if execution_time_ms > 5000:  # 5秒超過
            log_level = "warning"
        
        log_data = {
            "query_type": query_type,
            "table_name": table_name,
            "execution_time_ms": execution_time_ms,
            "rows_affected": rows_affected,
            "query_hash": query_hash,
            "performance_category": self._categorize_performance(execution_time_ms)
        }
        
        if log_level == "warning":
            self.warning("Slow query detected", **log_data)
        else:
            self.info("Database query executed", **log_data)
    
    def log_connection_event(self, event_type: str, connection_pool_size: int):
        """接続イベントログ"""
        
        self.info(
            "Database connection event",
            event_type=event_type,
            connection_pool_size=connection_pool_size,
            timestamp=datetime.utcnow().isoformat()
        )
    
    def log_bigquery_cost(
        self,
        query_hash: str,
        bytes_processed: int,
        estimated_cost_usd: float
    ):
        """BigQueryコストログ"""
        
        log_level = "info"
        if estimated_cost_usd > 0.01:  # 1セント超過
            log_level = "warning"
        
        log_data = {
            "query_hash": query_hash,
            "bytes_processed": bytes_processed,
            "estimated_cost_usd": estimated_cost_usd,
            "cost_category": self._categorize_cost(estimated_cost_usd)
        }
        
        if log_level == "warning":
            self.warning("High cost query detected", **log_data)
        else:
            self.info("BigQuery cost tracking", **log_data)
    
    def _categorize_performance(self, execution_time_ms: float) -> str:
        """パフォーマンス分類"""
        if execution_time_ms < 100:
            return "fast"
        elif execution_time_ms < 1000:
            return "normal"
        elif execution_time_ms < 5000:
            return "slow"
        else:
            return "very_slow"
    
    def _categorize_cost(self, cost_usd: float) -> str:
        """コスト分類"""
        if cost_usd < 0.001:
            return "low"
        elif cost_usd < 0.01:
            return "medium"
        else:
            return "high"
```

### 4. セキュリティログ
```python
# src/logging/security_logger.py
class SecurityLogger(StructuredLogger):
    """セキュリティ専用ログ"""
    
    def __init__(self):
        super().__init__("security", LogCategory.SECURITY)
    
    def log_authentication_attempt(
        self,
        client_ip: str,
        user_agent: str,
        success: bool,
        failure_reason: str = None
    ):
        """認証試行ログ"""
        
        if success:
            self.info(
                "Authentication successful",
                client_ip=client_ip,
                user_agent=user_agent,
                event_type="auth_success"
            )
        else:
            self.warning(
                "Authentication failed",
                client_ip=client_ip,
                user_agent=user_agent,
                failure_reason=failure_reason,
                event_type="auth_failure"
            )
    
    def log_suspicious_activity(
        self,
        activity_type: str,
        client_ip: str,
        details: Dict,
        risk_score: int
    ):
        """疑わしいアクティビティログ"""
        
        log_level = "warning" if risk_score < 70 else "error"
        
        log_data = {
            "activity_type": activity_type,
            "client_ip": client_ip,
            "risk_score": risk_score,
            "details": details,
            "requires_investigation": risk_score >= 70
        }
        
        if log_level == "error":
            self.error("High risk activity detected", **log_data)
        else:
            self.warning("Suspicious activity detected", **log_data)
    
    def log_data_access(
        self,
        data_type: str,
        access_level: str,
        client_ip: str,
        success: bool
    ):
        """データアクセスログ"""
        
        self.info(
            "Data access event",
            data_type=data_type,
            access_level=access_level,
            client_ip=client_ip,
            access_granted=success,
            event_type="data_access"
        )
```

## 🎯 ログ活用設計

### 1. アラート設定
```python
# src/monitoring/log_alerts.py
class LogBasedAlerts:
    """ログベースアラート"""
    
    ALERT_RULES = [
        {
            "name": "high_co2_alert",
            "condition": "current_co2_ppm > 1200",
            "severity": "warning",
            "notification": ["email", "slack"]
        },
        {
            "name": "api_error_rate",
            "condition": "error_rate_5min > 0.05",  # 5%エラー率
            "severity": "critical",
            "notification": ["email", "slack", "pagerduty"]
        },
        {
            "name": "slow_query_alert",
            "condition": "execution_time_ms > 10000",
            "severity": "warning",
            "notification": ["slack"]
        }
    ]
    
    @staticmethod
    def check_alert_conditions(log_entry: Dict) -> List[str]:
        """アラート条件チェック"""
        triggered_alerts = []
        
        for rule in LogBasedAlerts.ALERT_RULES:
            if LogBasedAlerts._evaluate_condition(rule["condition"], log_entry):
                triggered_alerts.append(rule["name"])
        
        return triggered_alerts
```

### 2. ログ分析クエリ
```sql
-- Cloud Logging用クエリ例

-- 1. エラー率監視
SELECT
  timestamp,
  COUNT(*) as total_requests,
  COUNTIF(status_code >= 400) as error_requests,
  COUNTIF(status_code >= 400) / COUNT(*) * 100 as error_rate
FROM logs
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
  AND jsonPayload.category = "api"
GROUP BY EXTRACT(MINUTE FROM timestamp)
ORDER BY timestamp DESC;

-- 2. CO2レベル分析
SELECT
  jsonPayload.current_co2_ppm as co2_level,
  jsonPayload.air_quality_status as status,
  COUNT(*) as frequency,
  AVG(jsonPayload.analysis_duration_ms) as avg_analysis_time
FROM logs
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 24 HOUR)
  AND jsonPayload.category = "business"
  AND jsonPayload.current_co2_ppm IS NOT NULL
GROUP BY co2_level, status
ORDER BY co2_level;

-- 3. パフォーマンス分析
SELECT
  jsonPayload.endpoint,
  COUNT(*) as request_count,
  AVG(jsonPayload.response_time_ms) as avg_response_time,
  PERCENTILE_CONT(jsonPayload.response_time_ms, 0.95) OVER() as p95_response_time
FROM logs
WHERE timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL 1 HOUR)
  AND jsonPayload.category = "api"
  AND jsonPayload.response_time_ms IS NOT NULL
GROUP BY jsonPayload.endpoint
ORDER BY avg_response_time DESC;
```

### 3. ダッシュボード設計
```python
# src/monitoring/dashboard_metrics.py
class DashboardMetrics:
    """ダッシュボード用メトリクス"""
    
    @staticmethod
    def get_api_health_metrics() -> Dict:
        """API健全性メトリクス"""
        return {
            "request_rate": "requests/minute",
            "error_rate": "percentage",
            "avg_response_time": "milliseconds",
            "p95_response_time": "milliseconds",
            "active_connections": "count"
        }
    
    @staticmethod
    def get_business_metrics() -> Dict:
        """ビジネスメトリクス"""
        return {
            "current_co2_level": "ppm",
            "air_quality_distribution": "percentage",
            "analysis_frequency": "analyses/hour",
            "data_quality_score": "percentage",
            "alert_frequency": "alerts/day"
        }
    
    @staticmethod
    def get_infrastructure_metrics() -> Dict:
        """インフラメトリクス"""
        return {
            "database_query_time": "milliseconds",
            "memory_usage": "percentage",
            "cpu_usage": "percentage",
            "bigquery_cost": "usd/day",
            "storage_usage": "bytes"
        }
```

## 🔧 ログ運用設計

### 1. ログレベル動的変更
```python
# src/logging/dynamic_config.py
class DynamicLogConfig:
    """動的ログ設定"""
    
    @staticmethod
    def change_log_level(logger_name: str, level: str):
        """ログレベル動的変更"""
        logger = logging.getLogger(logger_name)
        logger.setLevel(getattr(logging, level.upper()))
    
    @staticmethod
    def enable_debug_mode(duration_minutes: int = 10):
        """デバッグモード有効化（一時的）"""
        # 全ログをDEBUGレベルに変更
        # 指定時間後に元に戻すスケジューリング
        pass
```

### 2. ログローテーション
```python
# src/logging/rotation_config.py
import logging.handlers

def setup_log_rotation():
    """ログローテーション設定"""
    
    handler = logging.handlers.TimedRotatingFileHandler(
        filename='logs/co2-api.log',
        when='midnight',
        interval=1,
        backupCount=30,  # 30日分保持
        encoding='utf-8'
    )
    
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    handler.setFormatter(formatter)
    
    return handler
```

## 📊 ログ監視・分析

### Cloud Logging統合
```yaml
# ログ集約設定（Cloud Logging）
logging:
  level: INFO
  structured: true
  outputs:
    - type: stdout
      format: json
    - type: cloud_logging
      project_id: monitoring-bedroom
      log_name: co2-monitoring-api
  
  filters:
    - name: sensitive_data
      pattern: "(password|secret|token)"
      action: redact
    
    - name: pii_protection
      pattern: "(email|phone|ip_address)"
      action: hash
```

### Grafana ダッシュボード設定
```json
{
  "dashboard": {
    "title": "CO2 Monitoring API Logs",
    "panels": [
      {
        "title": "API Request Rate",
        "type": "graph",
        "targets": [
          {
            "expr": "rate(api_requests_total[5m])",
            "legendFormat": "{{endpoint}}"
          }
        ]
      },
      {
        "title": "CO2 Level Distribution",
        "type": "pie",
        "targets": [
          {
            "query": "category=\"business\" AND current_co2_ppm IS NOT NULL",
            "groupBy": "co2_level_category"
          }
        ]
      }
    ]
  }
}
```

この包括的なログ設計により、CO2モニタリングAPIの運用、監視、分析が効果的に実施できるようになります。