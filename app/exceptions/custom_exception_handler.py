from fastapi import Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


async def request_validation_handler(request: Request, exc: RequestValidationError):
    formatted_errors = {}

    for error in exc.errors():
        field_name = ".".join(map(str, error["loc"]))
        message = error["msg"]
        formatted_errors[field_name] = message

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        content={
            "detail": {
                "message": "request validation failed, please check the request body",
                "errors": formatted_errors,
            }
        },
    )
