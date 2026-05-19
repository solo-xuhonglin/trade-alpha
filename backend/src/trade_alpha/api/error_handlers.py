"""Global exception handlers for FastAPI application."""

from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from trade_alpha.api.exceptions import (
    TradeAlphaException,
    NotFoundException,
    BadRequestException,
    ConflictException,
    UnauthorizedException,
    ForbiddenException,
    ValidationException,
)
from trade_alpha.logging import get_logger

logger = get_logger("api_error_handler")


def _create_error_response(
    status_code: int,
    error_code: str,
    detail: str,
    field_errors: dict | None = None,
) -> dict:
    """Create standardized error response structure."""
    response = {
        "success": False,
        "error": {
            "code": error_code,
            "message": detail,
        }
    }
    if field_errors:
        response["error"]["fields"] = field_errors
    return response


async def trade_alpha_exception_handler(
    request: Request,
    exc: TradeAlphaException,
) -> JSONResponse:
    """Handle TradeAlpha custom exceptions."""
    logger.error(
        f"TradeAlphaException: {exc.error_code} - {exc.detail}",
        exc_info=True,
    )
    
    field_errors = getattr(exc, "field_errors", None)
    
    return JSONResponse(
        status_code=exc.status_code,
        content=_create_error_response(
            status_code=exc.status_code,
            error_code=exc.error_code,
            detail=exc.detail,
            field_errors=field_errors,
        )
    )


async def http_exception_handler(
    request: Request,
    exc: StarletteHTTPException,
) -> JSONResponse:
    """Handle Starlette HTTP exceptions."""
    logger.error(
        f"HTTPException: {exc.status_code} - {exc.detail}",
        exc_info=True,
    )
    
    error_code_map = {
        status.HTTP_400_BAD_REQUEST: "BAD_REQUEST",
        status.HTTP_401_UNAUTHORIZED: "UNAUTHORIZED",
        status.HTTP_403_FORBIDDEN: "FORBIDDEN",
        status.HTTP_404_NOT_FOUND: "NOT_FOUND",
        status.HTTP_405_METHOD_NOT_ALLOWED: "METHOD_NOT_ALLOWED",
        status.HTTP_409_CONFLICT: "CONFLICT",
        status.HTTP_422_UNPROCESSABLE_ENTITY: "VALIDATION_ERROR",
        status.HTTP_500_INTERNAL_SERVER_ERROR: "INTERNAL_ERROR",
    }
    
    error_code = error_code_map.get(exc.status_code, "HTTP_ERROR")
    detail = str(exc.detail) if exc.detail else "An error occurred"
    
    return JSONResponse(
        status_code=exc.status_code,
        content=_create_error_response(
            status_code=exc.status_code,
            error_code=error_code,
            detail=detail,
        )
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    """Handle FastAPI request validation exceptions."""
    logger.error(
        f"ValidationException: {exc.errors()}",
        exc_info=True,
    )
    
    # Format field errors
    field_errors = {}
    for error in exc.errors():
        # Get field name from loc
        field = ".".join(str(x) for x in error["loc"] if x != "body")
        if not field:
            field = "body"
        field_errors[field] = error["msg"]
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_create_error_response(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            error_code="VALIDATION_ERROR",
            detail="Request validation failed",
            field_errors=field_errors,
        )
    )


async def general_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    """Handle all uncaught exceptions."""
    logger.critical(
        f"UncaughtException: {type(exc).__name__} - {str(exc)}",
        exc_info=True,
    )
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_create_error_response(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            error_code="INTERNAL_ERROR",
            detail="An unexpected error occurred",
        )
    )


def register_exception_handlers(app):
    """Register all exception handlers with FastAPI application."""
    app.add_exception_handler(TradeAlphaException, trade_alpha_exception_handler)
    app.add_exception_handler(NotFoundException, trade_alpha_exception_handler)
    app.add_exception_handler(BadRequestException, trade_alpha_exception_handler)
    app.add_exception_handler(ConflictException, trade_alpha_exception_handler)
    app.add_exception_handler(UnauthorizedException, trade_alpha_exception_handler)
    app.add_exception_handler(ForbiddenException, trade_alpha_exception_handler)
    app.add_exception_handler(ValidationException, trade_alpha_exception_handler)
    
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    
    app.add_exception_handler(Exception, general_exception_handler)
