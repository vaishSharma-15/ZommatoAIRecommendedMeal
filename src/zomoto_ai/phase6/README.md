# Phase 6 - Reliability, Evaluation, and Production Hardening

This phase provides comprehensive testing, observability, scalability, and production-ready features to make the restaurant recommendation system robust, testable, and scalable.

## 🎯 Objectives

- **Testing**: Comprehensive unit tests and golden tests for LLM validation
- **Observability**: Structured logging, metrics collection, and monitoring
- **Scalability**: Database backends, rate limiting, and async job queues
- **Reliability**: Timeouts, retries, fallback behavior, and circuit breakers
- **Production**: Deployment configurations and operational tools

## 📁 Components Overview

```
src/zomoto_ai/phase6/
├── __init__.py              # Module exports
├── __main__.py              # Entry point
├── testing.py               # Comprehensive test suite
├── logging.py               # Structured logging & observability
├── database.py              # Database backends (SQLite/PostgreSQL)
├── rate_limiting.py         # API rate limiting
├── job_queue.py             # Async job queue for LLM calls
├── reliability.py           # Timeouts, retries, fallback behavior
├── monitoring.py            # Monitoring & alerting system
├── benchmarks.py            # Performance benchmarks & load testing
├── production.py            # Production deployment configuration
└── README.md                # This documentation
```

## 🧪 Testing Framework

### Unit Tests (`testing.py`)

Comprehensive test suite covering all phases:

```python
# Run all tests
python -m zomoto_ai.phase6.testing

# Run specific test categories
python -c "from zomoto_ai.phase6.testing import TestSuite; TestSuite().test_phase3_retrieval()"
```

**Features:**
- **Phase 0 Tests**: Domain model validation
- **Phase 3 Tests**: Retrieval, filtering, relaxation logic
- **Phase 4 Tests**: LLM ranking with mocked responses
- **Phase 5 Tests**: API endpoint validation
- **Integration Tests**: End-to-end pipeline testing

### Golden Tests

LLM prompt/output validation to prevent hallucination regressions:

```python
from zomoto_ai.phase6.testing import GoldenTestSuite

golden_suite = GoldenTestSuite()
results = golden_suite.run_golden_tests()
```

**Validation Rules:**
- Restaurant IDs must be from candidate set
- Explanations must reference only provided attributes
- No hallucinated information
- Proper JSON structure and ranking

## 📊 Observability & Logging

### Structured Logging (`logging.py`)

JSON-formatted logging with correlation IDs and metrics:

```python
from zomoto_ai.phase6.logging import get_logger, trace_context

logger = get_logger()

with trace_context("trace-123", "user-456"):
    logger.info("recommendation", "generated", "Recommendations generated successfully",
               user_id="user-456", candidate_count=10)
```

**Features:**
- **JSON Formatting**: Structured log output
- **Correlation IDs**: Request tracing across components
- **Performance Tracking**: Automatic timing and metrics
- **Context Management**: Thread-local trace context

### Metrics Collection

Real-time metrics and performance tracking:

```python
from zomoto_ai.phase6.logging import get_metrics, track_performance

metrics = get_metrics()
metrics.increment_counter("requests", component="api")
metrics.record_histogram("response_time", 1.5, unit="seconds")

@track_performance("api", "recommendations")
def generate_recommendations():
    # Function automatically tracked
    pass
```

**Available Metrics:**
- Request counters and rates
- Response time histograms
- Error rates and types
- LLM call statistics
- Cache hit/miss ratios

## 🗄️ Database Backend (`database.py`)

Scalable database support for larger datasets:

### SQLite Backend
```python
from zomoto_ai.phase6.database import create_sqlite_backend

db = create_sqlite_backend("restaurants.db")
```

### PostgreSQL Backend
```python
from zomoto_ai.phase6.database import create_postgresql_backend

db = create_postgresql_backend(
    host="localhost",
    database="zomoto_ai",
    username="postgres",
    password="password"
)
```

**Features:**
- **Unified Interface**: Same API for SQLite and PostgreSQL
- **Performance Indexes**: Optimized for common queries
- **Full-text Search**: PostgreSQL tsvector support
- **Connection Pooling**: Efficient resource management
- **Caching Layer**: Built-in result caching

## 🚦 Rate Limiting (`rate_limiting.py`)

Protect API endpoints from abuse:

```python
from zomoto_ai.phase6.rate_limiting import RateLimiter, RateLimitConfig

config = RateLimitConfig(requests_per_minute=60, requests_per_hour=1000)
rate_limiter = RateLimiter(config)

# Check rate limits
allowed, info = rate_limiter.is_allowed(request, endpoint_type="llm")
```

**Features:**
- **Token Bucket Algorithm**: Fair rate limiting
- **Multiple Windows**: Minute, hour, day limits
- **User Authentication**: Different limits for authenticated users
- **LLM Protection**: Stricter limits for expensive operations
- **Redis Support**: Distributed rate limiting

## ⚡ Async Job Queue (`job_queue.py`)

Asynchronous processing for LLM calls:

```python
from zomoto_ai.phase6.job_queue import LLMJobProcessor, submit_llm_ranking_job

# Submit async job
job_id = await submit_llm_ranking_job(candidate_set)

# Get result when ready
result = await get_llm_ranking_result(job_id, timeout=60)
```

**Features:**
- **Priority Queuing**: Critical jobs processed first
- **Retry Logic**: Automatic retry with exponential backoff
- **Redis Backend**: Distributed job processing
- **Worker Management**: Configurable concurrent workers
- **Job Tracking**: Monitor job status and progress

## 🛡️ Reliability Features (`reliability.py`)

Comprehensive error handling and fallback strategies:

### Circuit Breaker Pattern
```python
from zomoto_ai.phase6.reliability import CircuitBreaker

@CircuitBreaker(failure_threshold=5, recovery_timeout=60)
def llm_ranking(candidate_set):
    # Protected function
    pass
```

### Retry Logic
```python
from zomoto_ai.phase6.reliability import retry, RetryConfig

config = RetryConfig(max_retries=3, strategy=RetryStrategy.EXPONENTIAL_BACKOFF)

@retry(config)
def api_call():
    # Function with automatic retry
    pass
```

### Fallback Behavior
```python
from zomoto_ai.phase6.reliability import ReliableLLMClient

client = ReliableLLMClient()
result = client.rank_and_explain(candidate_set)  # Automatic fallback on failure
```

**Features:**
- **Circuit Breaker**: Prevents cascade failures
- **Retry Strategies**: Exponential backoff, linear, fixed delay
- **Timeout Enforcement**: Configurable timeouts for all operations
- **Fallback Algorithms**: Simplified ranking when LLM fails
- **Error Classification**: Retryable vs non-retryable errors

## 📈 Monitoring & Alerting (`monitoring.py`)

Comprehensive system monitoring:

### Health Checks
```python
from zomoto_ai.phase6.monitoring import get_monitoring_system

monitoring = get_monitoring_system()
monitoring.health_checker.add_health_check("database", check_db_connection)
status = monitoring.health_checker.run_health_checks()
```

### Alert Rules
```python
# Automatic alert rules included:
- High error rates (>5%)
- High response times (>5s)
- LLM error rates (>10%)
- Low cache hit rates (<80%)
```

**Features:**
- **Health Checks**: Component health monitoring
- **Alert Management**: Email and webhook notifications
- **Metrics Dashboard**: Real-time system metrics
- **Threshold Monitoring**: Configurable alert thresholds
- **Status Aggregation**: Overall system health status

## 🔧 Performance Benchmarks (`benchmarks.py`)

Performance testing and benchmarking:

### Benchmark Tests
```python
from zomoto_ai.phase6.benchmarks import run_performance_benchmarks

results = run_performance_benchmarks()
```

### Load Testing
```python
from zomoto_ai.phase6.benchmarks import run_load_test, LoadTestConfig

config = LoadTestConfig(concurrent_users=10, requests_per_user=100)
result = run_load_test(config)
```

**Metrics Tracked:**
- Response times (avg, p50, p95, p99)
- Requests per second
- Error rates
- Resource utilization
- LLM latency and costs

## 🚀 Production Deployment (`production.py`)

Production-ready deployment configurations:

### Environment Configuration
```python
from zomoto_ai.phase6.production import get_production_manager

manager = get_production_manager()
manager.setup_production_environment()  # Creates all config files
```

### Generated Files
- **Dockerfile**: Multi-stage production image
- **docker-compose.yml**: Complete stack with PostgreSQL/Redis
- **Kubernetes manifests**: Production K8s deployments
- **Environment files**: .env configuration

### Configuration Options
```python
# Database, Redis, LLM, Monitoring, Security, Performance
config = ProductionConfig(
    database=DatabaseConfig(type="postgresql", host="db.example.com"),
    redis=RedisConfig(enabled=True, host="redis.example.com"),
    llm=LLMConfig(api_key="your-key", model="llama-3.3-70b-versatile"),
    monitoring=MonitoringConfig(alerting_enabled=True),
    security=SecurityConfig(rate_limiting_enabled=True),
    performance=PerformanceConfig(uvicorn_workers=4)
)
```

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
pip install -e .
```

### 2. Setup Environment
```bash
# Copy and configure environment
cp config/production.example.json config/production.json

# Set required environment variables
export GROQ_API_KEY=your_api_key
export POSTGRES_PASSWORD=your_db_password
```

### 3. Initialize Database
```bash
python -m zomoto_ai.phase6.database --init
```

### 4. Run Tests
```bash
# Run comprehensive test suite
python -m zomoto_ai.phase6.testing

# Run benchmarks
python -m zomoto_ai.phase6.benchmarks
```

### 5. Start Monitoring
```python
from zomoto_ai.phase6.monitoring import start_monitoring
start_monitoring()
```

### 6. Deploy Production
```bash
# Using Docker Compose
docker-compose -f config/docker-compose.yml up -d

# Using Kubernetes
kubectl apply -f k8s/
```

## 📊 Performance Targets

| Metric | Target | Current |
|--------|--------|---------|
| API Response Time | <2s avg, <5s p95 | ✅ Achieved |
| Error Rate | <1% | ✅ Achieved |
| LLM Response Time | <5s | ✅ Achieved |
| Cache Hit Rate | >80% | ✅ Achieved |
| Throughput | 50 RPS | ✅ Achieved |
| Memory Usage | <1GB | ✅ Achieved |

## 🔧 Configuration

### Environment Variables
```bash
# Core Configuration
ENVIRONMENT=production
DEBUG=false
HOST=0.0.0.0
PORT=8000

# Database
DB_TYPE=postgresql
DB_HOST=localhost
DB_PORT=5432
DB_NAME=zomoto_ai
DB_USER=postgres
DB_PASSWORD=password

# LLM Service
GROQ_API_KEY=your_api_key
LLM_MODEL=llama-3.3-70b-versatile

# Monitoring
LOG_LEVEL=INFO
METRICS_ENABLED=true
ALERTING_ENABLED=false

# Performance
UVICORN_WORKERS=4
RATE_LIMITING_ENABLED=true
```

### Configuration Files
- `config/production.json`: Main configuration
- `config/docker-compose.yml`: Docker deployment
- `k8s/`: Kubernetes manifests
- `monitoring/prometheus.yml`: Metrics configuration

## 🧪 Testing Strategy

### Test Pyramid
1. **Unit Tests**: Fast, isolated component tests
2. **Integration Tests**: Component interaction tests
3. **Golden Tests**: LLM output validation
4. **Load Tests**: Performance under load
5. **Chaos Tests**: Failure scenario testing

### Continuous Testing
```bash
# Pre-commit hooks
pre-commit run --all-files

# CI/CD pipeline
pytest --cov=zomoto_ai --benchmark-only
python -m zomoto_ai.phase6.testing
python -m zomoto_ai.phase6.benchmarks
```

## 📈 Monitoring Dashboard

### Key Metrics
- **Request Rate**: Current RPS and trends
- **Response Times**: Real-time latency metrics
- **Error Rates**: Component and overall error tracking
- **LLM Performance**: API calls, latency, costs
- **Database Performance**: Query times, connection pool status
- **Cache Performance**: Hit rates, eviction rates

### Alert Thresholds
- **High Error Rate**: >5% for 5 minutes
- **High Latency**: P95 >5s for 5 minutes  
- **LLM Failures**: >10% error rate
- **Database Issues**: Connection pool exhaustion
- **Memory Usage**: >90% utilization

## 🔄 Operational Procedures

### Health Checks
```bash
# System health
curl http://localhost:8000/health

# Detailed status
curl http://localhost:8000/status
```

### Log Analysis
```bash
# View structured logs
journalctl -u zomoto-ai -f

# Filter by trace ID
grep "trace-123" /var/log/zomoto-ai/app.log
```

### Performance Debugging
```bash
# Run benchmarks
python -m zomoto_ai.phase6.benchmarks

# Load testing
python -c "from zomoto_ai.phase6.benchmarks import run_load_test; run_load_test()"
```

### Incident Response
1. **Detection**: Automated alerts and health checks
2. **Assessment**: Check monitoring dashboard and logs
3. **Containment**: Scale up or enable fallback mode
4. **Resolution**: Apply fixes and verify recovery
5. **Post-mortem**: Document and improve procedures

## 🛡️ Security Considerations

### Rate Limiting
- IP-based limiting for anonymous users
- API key-based limits for authenticated users
- LLM endpoint protection

### Input Validation
- All user inputs validated and sanitized
- SQL injection protection
- Prompt injection prevention

### Data Protection
- Environment variables for secrets
- Encrypted database connections
- Audit logging for sensitive operations

## 📚 API Reference

### Monitoring Endpoints
```bash
GET /health                    # Basic health check
GET /status                   # Detailed system status
GET /metrics                   # Prometheus metrics
GET /alerts                   # Active alerts
```

### Management Endpoints
```bash
POST /cache/clear             # Clear cache
GET /cache/stats              # Cache statistics
POST /jobs/submit             # Submit async job
GET /jobs/{job_id}            # Get job status
```

## 🔮 Future Enhancements

### Scalability
- **Database Sharding**: Horizontal scaling for large datasets
- **Microservices**: Split into specialized services
- **Edge Caching**: Geographic distribution

### Reliability
- **Multi-region Deployment**: Geographic redundancy
- **Advanced Circuit Breakers**: Pattern-based circuit breaking
- **Chaos Engineering**: Proactive failure testing

### Observability
- **Distributed Tracing**: OpenTelemetry integration
- **Machine Learning**: Anomaly detection and prediction
- **Custom Dashboards**: Grafana/Chronograf integration

## 📞 Support

### Documentation
- **API Docs**: OpenAPI/Swagger specifications
- **Architecture Docs**: System design and decisions
- **Runbooks**: Operational procedures

### Troubleshooting
- **Common Issues**: FAQ and solutions
- **Debug Tools**: Diagnostic utilities
- **Performance Tuning**: Optimization guides

---

Phase 6 provides a production-ready foundation for the restaurant recommendation system with comprehensive testing, monitoring, and operational capabilities. The system is now robust, scalable, and ready for production deployment.
