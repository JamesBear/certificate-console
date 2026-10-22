"""Uniform error envelope: {"error": {"code", "message", "details"}}."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

log = logging.getLogger("certificate_console")


class ApiError(Exception):
    def __init__(self, code: str, message: str, status: int = 400, details=None) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status
        self.details = details

    def body(self) -> dict:
        payload = {"code": self.code, "message": self.message}
        if self.details is not None:
            payload["details"] = self.details
        return {"error": payload}


def not_found(what: str = "Resource") -> ApiError:
    # 404 for anything outside the caller's tenant: a 403 would confirm it exists.
    return ApiError("not_found", f"{what} not found.", 404)


def forbidden(message: str = "You do not have permission to do that.") -> ApiError:
    return ApiError("forbidden", message, 403)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(status_code=exc.status, content=exc.body())

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unhandled error: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "internal_error", "message": "Something went wrong."}},
        )
