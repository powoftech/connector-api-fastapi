from typing import Annotated

import redis
from fastapi import Depends

from app.config import get_settings

r = redis.from_url(url=get_settings().redis_url)


def get_redis():
    yield r


RedisDep = Annotated[redis.Redis, Depends(get_redis)]

# pipe = r.pipeline()


# def get_pipe():
#     yield pipe


# PipeDep = Annotated[redis.client.Pipeline, Depends(get_pipe)]
