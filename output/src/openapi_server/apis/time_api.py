# coding: utf-8

from typing import Dict, List  # noqa: F401
import importlib
import pkgutil

from openapi_server.apis.time_api_base import BaseTimeApi
import openapi_server.impl

from fastapi import (  # noqa: F401
    APIRouter,
    Body,
    Cookie,
    Depends,
    Form,
    Header,
    HTTPException,
    Path,
    Query,
    Response,
    Security,
    status,
)

from openapi_server.models.extra_models import TokenModel  # noqa: F401
from openapi_server.models.get_current_time200_response import GetCurrentTime200Response


router = APIRouter()

ns_pkg = openapi_server.impl
for _, name, _ in pkgutil.iter_modules(ns_pkg.__path__, ns_pkg.__name__ + "."):
    importlib.import_module(name)


@router.get(
    "/time",
    responses={
        200: {"model": GetCurrentTime200Response, "description": "Successful response"},
    },
    tags=["time"],
    summary="Get current time in JST",
    response_model_by_alias=True,
)
async def get_current_time() -> GetCurrentTime200Response:
    """Returns the current time in Japan Standard Time (JST)"""
    if not BaseTimeApi.subclasses:
        raise HTTPException(status_code=500, detail="Not implemented")
    return await BaseTimeApi.subclasses[0]().get_current_time()
