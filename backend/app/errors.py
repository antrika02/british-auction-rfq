from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


class AppError(Exception):
    def __init__(self, code: str, message: str, status: int = 400):
        super().__init__(message)
        self.code = code
        self.message = message
        self.status = status


def _body(code: str, message: str, details: list | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _app_error(_: Request, exc: AppError):
        return JSONResponse(_body(exc.code, exc.message), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        details = []
        for err in exc.errors():
            field = ".".join(str(p) for p in err["loc"] if p != "body")
            message = err["msg"].removeprefix("Value error, ")
            details.append({"field": field, "message": message})
        first = details[0]["message"] if details else "Invalid request"
        return JSONResponse(_body("VALIDATION_ERROR", first, details), status_code=422)
