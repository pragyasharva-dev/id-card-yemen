"""
Prometheus Metrics Endpoint for e-KYC API.

Exposes application metrics in Prometheus format at /metrics.
"""
import time
import logging
from fastapi import APIRouter, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

try:
    from prometheus_client import Counter, Histogram, generate_latest, CONTENT_TYPE_LATEST
    PROMETHEUS_AVAILABLE = True
except ImportError:
    PROMETHEUS_AVAILABLE = False
    
logger = logging.getLogger(__name__)

router = APIRouter()

if PROMETHEUS_AVAILABLE:
    # Define metrics
    REQUEST_COUNT = Counter(
        "ekyc_requests_total",
        "Total number of requests",
        ["method", "endpoint", "status_code"]
    )
    REQUEST_LATENCY = Histogram(
        "ekyc_request_latency_seconds",
        "Request latency in seconds",
        ["method", "endpoint"],
        buckets=[0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]
    )
    
    class MetricsMiddleware(BaseHTTPMiddleware):
        """Middleware to collect request metrics."""
        
        async def dispatch(self, request: Request, call_next):
            # Skip metrics collection for /metrics endpoint itself
            if request.url.path == "/metrics":
                return await call_next(request)
            
            start_time = time.time()
            response = await call_next(request)
            latency = time.time() - start_time
            
            # Normalize endpoint (remove IDs for grouping)
            endpoint = request.url.path
            
            REQUEST_COUNT.labels(
                method=request.method,
                endpoint=endpoint,
                status_code=response.status_code
            ).inc()
            
            REQUEST_LATENCY.labels(
                method=request.method,
                endpoint=endpoint
            ).observe(latency)
            
            return response
    
    @router.get("/metrics", include_in_schema=False)
    async def metrics():
        """Prometheus metrics endpoint."""
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )
else:
    # Fallback when prometheus_client not installed
    class MetricsMiddleware(BaseHTTPMiddleware):
        """No-op middleware when prometheus not available."""
        async def dispatch(self, request: Request, call_next):
            return await call_next(request)
    
    @router.get("/metrics", include_in_schema=False)
    async def metrics():
        """Metrics endpoint (prometheus not available)."""
        return {"error": "prometheus_client not installed"}
