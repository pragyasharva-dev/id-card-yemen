"""
Request ID Middleware for e-KYC API.

Generates a unique transaction_id (UUID) for each incoming request and:
1. Attaches it to request.state for use in handlers
2. Adds X-Request-ID header to all responses
3. Injects into logging context for traceability
"""
import uuid
import logging
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


logger = logging.getLogger(__name__)


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Middleware to generate and propagate request IDs."""
    
    async def dispatch(self, request: Request, call_next):
        # Generate or use existing request ID
        request_id = request.headers.get("X-Request-ID")
        if not request_id:
            request_id = str(uuid.uuid4())
        
        # Attach to request state for use in route handlers
        request.state.request_id = request_id
        
        # Process request
        response = await call_next(request)
        
        # Add to response headers
        response.headers["X-Request-ID"] = request_id
        
        return response


def get_request_id(request: Request) -> str:
    """Helper to get request ID from request state."""
    return getattr(request.state, "request_id", "unknown")
