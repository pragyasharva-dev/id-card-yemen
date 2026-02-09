"""
API Key Authentication Middleware for e-KYC API.

Validates X-API-Key header against configured API keys.
Excludes public endpoints like /health, /metrics, /docs from authentication.
"""
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse


logger = logging.getLogger(__name__)

# Endpoints that don't require authentication
PUBLIC_PATHS = {
    "/",
    "/docs",
    "/redoc", 
    "/openapi.json",
    "/api/v1/health",
    "/metrics",
    "/static",
}


class APIKeyMiddleware(BaseHTTPMiddleware):
    """Middleware to validate API key authentication."""
    
    def __init__(self, app, api_keys: list[str] = None):
        """
        Initialize API Key middleware.
        
        Args:
            app: ASGI application
            api_keys: List of valid API keys. If empty/None, auth is disabled.
        """
        super().__init__(app)
        self.api_keys = set(api_keys) if api_keys else set()
        self.auth_enabled = len(self.api_keys) > 0
        
        if self.auth_enabled:
            logger.info(f"API Key authentication enabled with {len(self.api_keys)} key(s)")
        else:
            logger.info("API Key authentication disabled (no keys configured)")
    
    async def dispatch(self, request: Request, call_next):
        # Skip auth if disabled
        if not self.auth_enabled:
            return await call_next(request)
        
        # Skip auth for public paths
        path = request.url.path
        if self._is_public_path(path):
            return await call_next(request)
        
        # Validate API key
        api_key = request.headers.get("X-API-Key")
        if not api_key:
            logger.warning(f"Missing API key for {request.method} {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "UNAUTHORIZED",
                    "message": "Missing X-API-Key header"
                }
            )
        
        if api_key not in self.api_keys:
            logger.warning(f"Invalid API key for {request.method} {path}")
            return JSONResponse(
                status_code=401,
                content={
                    "error": "UNAUTHORIZED",
                    "message": "Invalid API key"
                }
            )
        
        return await call_next(request)
    
    def _is_public_path(self, path: str) -> bool:
        """Check if path is in the public (no-auth) list."""
        # Exact match
        if path in PUBLIC_PATHS:
            return True
        # Prefix match for static files
        if path.startswith("/static/"):
            return True
        return False
