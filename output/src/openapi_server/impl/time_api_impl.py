# coding: utf-8

from datetime import datetime
import pytz

from openapi_server.apis.time_api_base import BaseTimeApi
from openapi_server.models.get_current_time200_response import GetCurrentTime200Response


class TimeApiImpl(BaseTimeApi):
    async def get_current_time(self) -> GetCurrentTime200Response:
        """Returns the current time in Japan Standard Time (JST)"""
        jst = pytz.timezone("Asia/Tokyo")
        current_time = datetime.now(jst)
        return GetCurrentTime200Response(current_time=current_time)
