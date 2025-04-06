# coding: utf-8

from datetime import datetime
import pytest
import pytz
from freezegun import freeze_time

from openapi_server.impl.time_api_impl import TimeApiImpl
from openapi_server.models.get_current_time200_response import GetCurrentTime200Response


@pytest.fixture
def time_api():
    return TimeApiImpl()


@pytest.mark.asyncio
async def test_レスポンスがJSTであることを確認():
    """
    シナリオ：
    1. TimeApiImplのget_current_timeメソッドを呼び出す
    2. レスポンスの型とタイムゾーンを確認する
    期待結果：
    - レスポンスがGetCurrentTime200Response型である
    - 時刻がdatetime型である
    - タイムゾーンがAsia/Tokyoである
    """
    api = TimeApiImpl()
    response = await api.get_current_time()

    assert isinstance(response, GetCurrentTime200Response)
    assert isinstance(response.current_time, datetime)

    # タイムゾーンがJSTであることを確認
    jst = pytz.timezone("Asia/Tokyo")
    assert response.current_time.tzinfo.zone == jst.zone


@pytest.mark.asyncio
@freeze_time("2024-04-06 12:00:00+09:00")
async def test_固定時刻での動作確認():
    """
    シナリオ：
    1. システム時刻を2024-04-06 12:00:00 JSTに固定
    2. TimeApiImplのget_current_timeメソッドを呼び出す
    期待結果：
    - 固定した時刻（2024-04-06 12:00:00 JST）が返される
    """
    api = TimeApiImpl()
    response = await api.get_current_time()

    expected = datetime(2024, 4, 6, 12, 0, 0, tzinfo=pytz.timezone("Asia/Tokyo"))
    assert response.current_time == expected


@pytest.mark.asyncio
async def test_JSTとUTCの時差が9時間であることを確認():
    """
    シナリオ：
    1. TimeApiImplのget_current_timeメソッドを呼び出す
    2. 返された時刻のUTCオフセットを確認
    期待結果：
    - UTCとの時差が9時間（32400秒）である
    """
    api = TimeApiImpl()
    response = await api.get_current_time()

    # UTCとの時差が9時間であることを確認
    offset = response.current_time.utcoffset()
    assert offset.total_seconds() == 9 * 60 * 60  # 9時間をsecondで表現
