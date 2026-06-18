# Issue #11: Cloud Run対応とデプロイ設定

## 📋 概要
CO2モニタリングAPIをCloud Runにデプロイするための設定を実装し、本番環境での運用を可能にする

## 🎯 目標
- Cloud Run用Dockerfileの作成
- 環境変数とシークレット管理
- サービスアカウント設定
- CI/CDパイプライン構築
- ヘルスチェックとモニタリング

## 📝 詳細要件

### Dockerfile作成

#### 1. マルチステージビルド
```dockerfile
# マルチステージビルド用Dockerfile
FROM python:3.11-slim as builder

# システム依存関係のインストール
RUN apt-get update && apt-get install -y \\
    gcc \\
    g++ \\
    && rm -rf /var/lib/apt/lists/*

# Python依存関係のインストール
COPY requirements.txt .
RUN pip install --no-cache-dir --user -r requirements.txt

# 本番イメージ
FROM python:3.11-slim

# 非rootユーザーの作成
RUN groupadd -r appgroup && useradd -r -g appgroup appuser

# 必要なシステムパッケージのインストール
RUN apt-get update && apt-get install -y \\
    curl \\
    && rm -rf /var/lib/apt/lists/*

# Python依存関係のコピー
COPY --from=builder /root/.local /home/appuser/.local
ENV PATH=/home/appuser/.local/bin:$PATH

# アプリケーションディレクトリの作成
WORKDIR /app

# アプリケーションコードのコピー
COPY src/ ./src/
COPY CLAUDE.md ./

# 権限設定
RUN chown -R appuser:appgroup /app
USER appuser

# ヘルスチェック
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \\
    CMD curl -f http://localhost:8080/api/air-quality/health || exit 1

# ポートの公開
EXPOSE 8080

# 環境変数
ENV PYTHONPATH=/app
ENV PORT=8080
ENV ENVIRONMENT=production

# アプリケーション起動
CMD [\"uvicorn\", \"src.openapi_server.main:app\", \"--host\", \"0.0.0.0\", \"--port\", \"8080\"]
```

#### 2. .dockerignore
```
# .dockerignore
__pycache__/
*.pyc
*.pyo
*.pyd
.Python
.pytest_cache/
.coverage
htmlcov/
.tox/
.cache
.venv/
venv/
node_modules/
.git/
.gitignore
README.md
docs/
tests/
*.log
.DS_Store
.env.local
.env.development
```

### 環境設定

#### 1. 本番用設定クラス
```python
# src/config/production_settings.py
import os
from pydantic_settings import BaseSettings
from typing import Optional

class ProductionSettings(BaseSettings):
    \"\"\"本番環境設定\"\"\"
    
    # 基本設定
    ENVIRONMENT: str = \"production\"
    DEBUG: bool = False
    LOG_LEVEL: str = \"INFO\"
    
    # BigQuery設定
    PROJECT_ID: str = \"monitoring-bedroom\"
    BIGQUERY_DATASET: str = \"room_temperature\"
    BIGQUERY_TABLE: str = \"bedroom_co2\"
    
    # API設定
    API_VERSION: str = \"1.0.0\"
    MAX_REQUEST_SIZE: int = 1048576  # 1MB
    REQUEST_TIMEOUT: int = 30
    
    # モニタリング設定
    ENABLE_METRICS: bool = True
    METRICS_PORT: int = 9090
    
    # セキュリティ設定
    ALLOWED_HOSTS: list = [\"*\"]  # 本番では具体的なドメインを指定
    CORS_ORIGINS: list = []
    
    # パフォーマンス設定
    WORKER_CONNECTIONS: int = 1000
    KEEP_ALIVE: int = 2
    
    # Google Cloud設定
    GOOGLE_CLOUD_PROJECT: Optional[str] = None
    
    class Config:
        env_file = \".env\"
        env_file_encoding = \"utf-8\"

def get_production_settings() -> ProductionSettings:
    return ProductionSettings()
```

#### 2. 環境別設定管理
```python
# src/config/settings_factory.py
import os
from typing import Union

from database.air_quality_config import AirQualitySettings
from config.production_settings import ProductionSettings

def get_settings() -> Union[AirQualitySettings, ProductionSettings]:
    \"\"\"環境に応じた設定を取得\"\"\"
    
    environment = os.getenv(\"ENVIRONMENT\", \"development\")
    
    if environment == \"production\":
        return ProductionSettings()
    else:
        return AirQualitySettings()
```

### Cloud Run用設定

#### 1. cloud-run.yaml
```yaml
# cloud-run.yaml
apiVersion: serving.knative.dev/v1
kind: Service
metadata:
  name: co2-monitoring-api
  annotations:
    run.googleapis.com/ingress: all
    run.googleapis.com/execution-environment: gen2
spec:
  template:
    metadata:
      annotations:
        # CPU とメモリの設定
        run.googleapis.com/cpu-throttling: \"false\"
        run.googleapis.com/memory: \"1Gi\"
        run.googleapis.com/cpu: \"1000m\"
        
        # スケーリング設定
        autoscaling.knative.dev/minScale: \"0\"
        autoscaling.knative.dev/maxScale: \"10\"
        
        # タイムアウト設定
        run.googleapis.com/timeout: \"300s\"
        
        # サービスアカウント
        run.googleapis.com/service-account: \"co2-api-service@monitoring-bedroom.iam.gserviceaccount.com\"
    spec:
      containerConcurrency: 100
      containers:
      - image: gcr.io/monitoring-bedroom/co2-monitoring-api:latest
        ports:
        - containerPort: 8080
        env:
        - name: ENVIRONMENT
          value: \"production\"
        - name: PROJECT_ID
          value: \"monitoring-bedroom\"
        - name: BIGQUERY_DATASET
          value: \"room_temperature\"
        - name: BIGQUERY_TABLE
          value: \"bedroom_co2\"
        - name: LOG_LEVEL
          value: \"INFO\"
        
        # リソース制限
        resources:
          limits:
            cpu: \"1000m\"
            memory: \"1Gi\"
          requests:
            cpu: \"500m\"
            memory: \"512Mi\"
        
        # ヘルスチェック
        livenessProbe:
          httpGet:
            path: /api/air-quality/health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 30
          timeoutSeconds: 10
          failureThreshold: 3
        
        readinessProbe:
          httpGet:
            path: /api/air-quality/health
            port: 8080
          initialDelaySeconds: 5
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
        
        # 起動プローブ
        startupProbe:
          httpGet:
            path: /api/air-quality/health
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 30
```

#### 2. サービスアカウント設定
```bash
# サービスアカウント作成とIAM設定
#!/bin/bash

PROJECT_ID=\"monitoring-bedroom\"
SA_NAME=\"co2-api-service\"
SA_DESCRIPTION=\"CO2 Monitoring API Service Account\"

# サービスアカウント作成
gcloud iam service-accounts create $SA_NAME \\
    --description=\"$SA_DESCRIPTION\" \\
    --display-name=\"CO2 API Service Account\" \\
    --project=$PROJECT_ID

# BigQuery権限付与
gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member=\"serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com\" \\
    --role=\"roles/bigquery.dataViewer\"

gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member=\"serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com\" \\
    --role=\"roles/bigquery.jobUser\"

# Cloud Logging権限
gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member=\"serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com\" \\
    --role=\"roles/logging.logWriter\"

# Cloud Monitoring権限
gcloud projects add-iam-policy-binding $PROJECT_ID \\
    --member=\"serviceAccount:$SA_NAME@$PROJECT_ID.iam.gserviceaccount.com\" \\
    --role=\"roles/monitoring.metricWriter\"
```

### CI/CDパイプライン

#### 1. GitHub Actions Workflow
```yaml
# .github/workflows/deploy-to-cloud-run.yml
name: Deploy to Cloud Run

on:
  push:
    branches: [ main ]
  pull_request:
    branches: [ main ]

env:
  PROJECT_ID: monitoring-bedroom
  GAR_LOCATION: asia-northeast1
  REPOSITORY: co2-monitoring
  SERVICE: co2-monitoring-api
  REGION: asia-northeast1

jobs:
  test:
    runs-on: ubuntu-latest
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.11'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-dev.txt
    
    - name: Run tests
      run: |
        pytest tests/ --cov=src --cov-report=xml
    
    - name: Upload coverage
      uses: codecov/codecov-action@v3
      with:
        file: ./coverage.xml

  deploy:
    needs: test
    runs-on: ubuntu-latest
    if: github.ref == 'refs/heads/main'
    
    permissions:
      contents: read
      id-token: write
    
    steps:
    - name: Checkout
      uses: actions/checkout@v4
    
    - name: Google Auth
      id: auth
      uses: 'google-github-actions/auth@v1'
      with:
        workload_identity_provider: '${{ secrets.WIF_PROVIDER }}'
        service_account: '${{ secrets.WIF_SERVICE_ACCOUNT }}'
    
    - name: Set up Cloud SDK
      uses: 'google-github-actions/setup-gcloud@v1'
    
    - name: Configure Docker to use gcloud
      run: gcloud auth configure-docker $GAR_LOCATION-docker.pkg.dev
    
    - name: Build and Push Container
      run: |
        docker build -t \"$GAR_LOCATION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:$GITHUB_SHA\" .
        docker push \"$GAR_LOCATION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$SERVICE:$GITHUB_SHA\"
    
    - name: Deploy to Cloud Run
      id: deploy
      uses: google-github-actions/deploy-cloudrun@v1
      with:
        service: ${{ env.SERVICE }}
        region: ${{ env.REGION }}
        image: ${{ env.GAR_LOCATION }}-docker.pkg.dev/${{ env.PROJECT_ID }}/${{ env.REPOSITORY }}/${{ env.SERVICE }}:${{ github.sha }}
    
    - name: Show Output
      run: echo ${{ steps.deploy.outputs.url }}
```

#### 2. デプロイスクリプト
```bash
#!/bin/bash
# deploy.sh

set -e

PROJECT_ID=\"monitoring-bedroom\"
SERVICE_NAME=\"co2-monitoring-api\"
REGION=\"asia-northeast1\"
IMAGE_NAME=\"gcr.io/$PROJECT_ID/$SERVICE_NAME\"

echo \"Building Docker image...\"
docker build -t $IMAGE_NAME:latest .

echo \"Pushing image to Container Registry...\"
docker push $IMAGE_NAME:latest

echo \"Deploying to Cloud Run...\"
gcloud run deploy $SERVICE_NAME \\
    --image $IMAGE_NAME:latest \\
    --platform managed \\
    --region $REGION \\
    --allow-unauthenticated \\
    --service-account \"co2-api-service@$PROJECT_ID.iam.gserviceaccount.com\" \\
    --memory 1Gi \\
    --cpu 1 \\
    --timeout 300 \\
    --concurrency 100 \\
    --min-instances 0 \\
    --max-instances 10 \\
    --set-env-vars=\"ENVIRONMENT=production,PROJECT_ID=$PROJECT_ID\"

echo \"Deployment completed!\"

# サービスURL取得
SERVICE_URL=$(gcloud run services describe $SERVICE_NAME --region=$REGION --format=\"value(status.url)\")
echo \"Service URL: $SERVICE_URL\"

# ヘルスチェック
echo \"Performing health check...\"
curl -f \"$SERVICE_URL/api/air-quality/health\" || exit 1

echo \"Health check passed!\"
```

### モニタリング設定

#### 1. Cloud Logging設定
```python
# src/logging/cloud_logging.py
import logging
import json
from google.cloud import logging as cloud_logging
from google.cloud.logging.handlers import CloudLoggingHandler

def setup_cloud_logging():
    \"\"\"Cloud Logging設定\"\"\"
    
    if os.getenv(\"ENVIRONMENT\") == \"production\":
        # Cloud Loggingクライアント
        client = cloud_logging.Client()
        handler = CloudLoggingHandler(client)
        
        # フォーマット設定
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        handler.setFormatter(formatter)
        
        # ルートロガー設定
        root_logger = logging.getLogger()
        root_logger.addHandler(handler)
        root_logger.setLevel(logging.INFO)
    else:
        # ローカル開発用
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )

class StructuredLogger:
    \"\"\"構造化ログ出力\"\"\"
    
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def log_api_metrics(
        self, 
        endpoint: str, 
        method: str, 
        status_code: int, 
        response_time: float,
        **kwargs
    ):
        \"\"\"API メトリクスログ\"\"\"
        
        log_data = {
            \"type\": \"api_metrics\",
            \"endpoint\": endpoint,
            \"method\": method,
            \"status_code\": status_code,
            \"response_time_ms\": response_time * 1000,
            \"timestamp\": datetime.now().isoformat(),
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data))
    
    def log_business_metrics(
        self, 
        co2_level: int, 
        status: str, 
        action: str,
        **kwargs
    ):
        \"\"\"ビジネスメトリクスログ\"\"\"
        
        log_data = {
            \"type\": \"business_metrics\",
            \"co2_level\": co2_level,
            \"status\": status,
            \"action\": action,
            \"timestamp\": datetime.now().isoformat(),
            **kwargs
        }
        
        self.logger.info(json.dumps(log_data))
```

#### 2. メトリクス収集
```python
# src/monitoring/metrics.py
from prometheus_client import Counter, Histogram, Gauge, start_http_server
import time
from functools import wraps

# メトリクス定義
REQUEST_COUNT = Counter(
    'http_requests_total',
    'Total HTTP requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'http_request_duration_seconds',
    'HTTP request duration',
    ['method', 'endpoint']
)

CO2_LEVEL_GAUGE = Gauge(
    'current_co2_level_ppm',
    'Current CO2 level in PPM'
)

API_ERRORS = Counter(
    'api_errors_total',
    'Total API errors',
    ['error_type']
)

def metrics_middleware(func):
    \"\"\"メトリクス収集ミドルウェア\"\"\"
    
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        
        try:
            result = await func(*args, **kwargs)
            REQUEST_COUNT.labels(
                method='GET',
                endpoint=func.__name__,
                status='success'
            ).inc()
            return result
            
        except Exception as e:
            REQUEST_COUNT.labels(
                method='GET',
                endpoint=func.__name__,
                status='error'
            ).inc()
            
            API_ERRORS.labels(error_type=type(e).__name__).inc()
            raise
            
        finally:
            REQUEST_DURATION.labels(
                method='GET',
                endpoint=func.__name__
            ).observe(time.time() - start_time)
    
    return wrapper

def start_metrics_server(port: int = 9090):
    \"\"\"メトリクスサーバー開始\"\"\"
    start_http_server(port)
```

## ✅ 完了条件
- [ ] Dockerfileの作成と最適化
- [ ] Cloud Run設定ファイル
- [ ] サービスアカウント設定
- [ ] CI/CDパイプライン構築
- [ ] ログとモニタリング設定
- [ ] デプロイスクリプト
- [ ] ヘルスチェック実装
- [ ] 本番環境テスト

## 🧪 デプロイテスト
```bash
# ローカルDockerテスト
docker build -t co2-api .
docker run -p 8080:8080 -e ENVIRONMENT=production co2-api

# Cloud Run デプロイテスト
./deploy.sh

# ヘルスチェック
curl https://co2-monitoring-api-xxx.a.run.app/api/air-quality/health

# 機能テスト
curl \"https://co2-monitoring-api-xxx.a.run.app/api/air-quality/co2-status?hours=3\"
```

## 📁 ファイル構成
```
.
├── Dockerfile                      # 新規作成
├── .dockerignore                   # 新規作成
├── cloud-run.yaml                  # 新規作成
├── deploy.sh                       # 新規作成
├── .github/
│   └── workflows/
│       └── deploy-to-cloud-run.yml # 新規作成
├── src/
│   ├── config/
│   │   ├── production_settings.py  # 新規作成
│   │   └── settings_factory.py     # 新規作成
│   ├── logging/
│   │   └── cloud_logging.py        # 新規作成
│   └── monitoring/
│       └── metrics.py               # 新規作成
└── scripts/
    └── setup-service-account.sh     # 新規作成
```

## 🔗 関連Issue
- 前のIssue: #10 単体テスト実装
- 次のIssue: #12 パフォーマンス最適化

## 🚀 デプロイフロー
1. **開発**: ローカル環境でテスト
2. **ビルド**: Dockerイメージ作成
3. **テスト**: 自動テスト実行
4. **デプロイ**: Cloud Runにデプロイ
5. **検証**: ヘルスチェックと機能テスト
6. **モニタリング**: ログとメトリクス監視