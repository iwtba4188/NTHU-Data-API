from enum import Enum
from typing import Annotated, Optional

from pydantic import BaseModel, BeforeValidator, Field, HttpUrl

from src.utils.schema import url_corrector


class DiningBuildingName(str, Enum):
    小吃部 = "小吃部"
    水木生活中心 = "水木生活中心"
    風雲樓 = "風雲樓"
    綜合教學大樓_南大校區 = "綜合教學大樓(南大校區)"
    其他餐廳 = "其他餐廳"


class DiningScheduleName(str, Enum):
    today = "today"
    weekday = "weekday"
    saturday = "saturday"
    sunday = "sunday"


class DiningRestaurant(BaseModel):
    area: str = Field(..., description="餐廳所在建築")
    image: Optional[Annotated[HttpUrl, BeforeValidator(url_corrector)]] = Field(
        ..., description="餐廳圖片"
    )
    name: str = Field(..., description="餐廳名稱")
    note: str = Field(..., description="餐廳備註")
    phone: str = Field(..., description="餐廳電話")
    schedule: dict = Field(..., description="餐廳營業時間")


class DiningBuilding(BaseModel):
    building: str = Field(..., description="建築名稱")
    restaurants: list[DiningRestaurant] = Field(..., description="餐廳資料")


class DiningScheduleKeyword:
    DAY_EN_TO_ZH = {
        "weekday": ["平日"],
        "saturday": ["週六", "星期六", "禮拜六", "六"],
        "sunday": ["週日", "星期日", "禮拜日", "日"],
    }
    BREAK_KEYWORDS = ["暫停營業", "休息", "休業", "休"]
