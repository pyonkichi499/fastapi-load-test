# coding: utf-8

from typing import ClassVar, Dict, List, Tuple  # noqa: F401

from openapi_server.models.get_current_time200_response import GetCurrentTime200Response


class BaseDefaultApi:
    subclasses: ClassVar[Tuple] = ()

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        BaseDefaultApi.subclasses = BaseDefaultApi.subclasses + (cls,)
    async def get_current_time(
        self,
    ) -> GetCurrentTime200Response:
        """Returns the current time in Japan Standard Time (JST)"""
        ...
