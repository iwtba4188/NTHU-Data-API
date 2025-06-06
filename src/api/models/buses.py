from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from functools import reduce
from itertools import product
from typing import Any, Literal, Optional

import pandas as pd

from src.api import schemas
from src.utils import nthudata

# ---------------------------------------------------------------------------
# 常數與全域變數
# ---------------------------------------------------------------------------
DATA_TTL_HOURS = 4  # 資料存活時間 (小時)

# 保持後續程式中 BUS_TYPE, BUS_DAY, BUS_DIRECTION 的順序一致，因 BusType、BusDay 具有 all 選項
BUS_ROUTE_TYPE: list[str] = [bus_type.value for bus_type in schemas.buses.BusRouteType]
BUS_ROUTE_TYPE_WITHOUT_ALL: list[str] = BUS_ROUTE_TYPE[1:]  # 第一個為 all，故移除
BUS_DAY: list[str] = [bus_day.value for bus_day in schemas.buses.BusDay]
BUS_DAY_WITHOUT_ALL: list[str] = BUS_DAY[1:]
BUS_DIRECTION: list[str] = [bus_dir.value for bus_dir in schemas.buses.BusDirection]

schedule_index = pd.MultiIndex.from_product([BUS_ROUTE_TYPE, BUS_DAY, BUS_DIRECTION])


# ---------------------------------------------------------------------------
# Helper Functions
# ---------------------------------------------------------------------------
def get_nested_value(data: dict, keys: list[str]) -> Any:
    """
    從巢狀字典中根據鍵路徑 (keys) 取得對應的值。

    Args:
        data (dict): 巢狀字典。
        keys (list[str]): 鍵路徑，依序指定巢狀結構中的鍵。

    Returns:
        Any: 根據鍵路徑取得的值。若路徑不存在，則返回 None。
    """
    return reduce(dict.get, keys, data)


def after_specific_time(
    target_list: list[dict], time_str: str, time_path: Optional[list[str]] = None
) -> list[dict]:
    """
    過濾字典列表，僅保留指定時間之後的資料。

    Args:
        target_list (list[dict]): 包含時間字串的字典列表。
        time_str (str): 比較用的時間字串，格式為 'HH:MM'。
        time_path (Optional[list[str]]): 指定在字典中取得時間字串的鍵路徑。
                                        若為 None，則預設字典本身即為時間字串。

    Returns:
        list[dict]: 過濾後的時間在 `time_str` 之後的字典列表。
    """
    ref_hour, ref_minute = map(int, time_str.split(":"))
    filtered_list = []
    for item in target_list:
        item_time_str = get_nested_value(item, time_path) if time_path else item
        item_hour, item_minute = map(int, item_time_str.split(":"))
        if item_hour > ref_hour or (
            item_hour == ref_hour and item_minute >= ref_minute
        ):
            filtered_list.append(item)
    return filtered_list


def sort_by_time(target: list[dict], time_path: Optional[list[str]] = None) -> None:
    """
    依照時間排序字典列表。

    Args:
        target (list[dict]): 包含時間資訊的字典列表。
        time_path (Optional[list[str]]): 指定在字典中取得時間字串的鍵路徑。
                                        若為 None，則預設字典本身即為時間字串。
        時間字串格式必須為 '%H:%M'。
    """
    target.sort(
        key=lambda x: datetime.strptime(
            get_nested_value(x, time_path) if time_path else x, "%H:%M"
        )
    )


def gen_the_all_field(target_dataframe: pd.DataFrame, time_path: list[str]) -> None:
    """
    針對 DataFrame 產品組合欄位，將資料合併至 'all' 欄位，並依照時間排序。

    此函式會針對 BUS_TYPE_WITHOUT_ALL 和 BUS_DAY，將 weekday 與 weekend 以及不同 BusType 的資料合併到 'all' 欄位，
    並確保最終的 'all' 欄位資料已按照時間排序。

    Args:
        target_dataframe (pd.DataFrame): 包含分層索引 (MultiIndex) 的 DataFrame，索引應包含 BUS_TYPE, BUS_DAY, BUS_DIRECTION。
        time_path (list[str]): 指定在資料中取得時間字串的鍵路徑，用於排序。
    """
    # 針對 BUS_TYPE_WITHOUT_ALL 合併 weekday 與 weekend
    for route_type, direction in product(BUS_ROUTE_TYPE_WITHOUT_ALL, BUS_DIRECTION):
        weekday_data = target_dataframe.loc[(route_type, "weekday", direction), "data"]
        weekend_data = target_dataframe.loc[(route_type, "weekend", direction), "data"]
        target_dataframe.loc[(route_type, "all", direction), "data"] = (
            weekday_data + weekend_data
        )

    # 合併不同 BusType 的資料
    for day, direction in product(BUS_DAY, BUS_DIRECTION):
        main_data = target_dataframe.loc[("main", day, direction), "data"]
        nanda_data = target_dataframe.loc[("nanda", day, direction), "data"]
        target_dataframe.loc[("all", day, direction), "data"] = main_data + nanda_data

    # 最後對所有資料依時間排序
    for route_type, day, direction in product(BUS_ROUTE_TYPE, BUS_DAY, BUS_DIRECTION):
        sort_by_time(
            target_dataframe.loc[(route_type, day, direction), "data"], time_path
        )


# ---------------------------------------------------------------------------
# 資料結構定義
# ---------------------------------------------------------------------------
@dataclass(unsafe_hash=True)
class Stop:
    """
    公車站點資料類別。

    Attributes:
        name (str): 站點名稱 (中文)。
        name_en (str): 站點英文名稱。
        latitude (str): 站點緯度。
        longitude (str): 站點經度。
        stopped_bus (pd.DataFrame): DataFrame 儲存停靠此站點的公車時刻表資料，初始化後設定，不參與比較或雜湊計算。
    """

    name: str
    name_en: str
    latitude: str
    longitude: str
    stopped_bus: pd.DataFrame = field(init=False, compare=False, hash=False)

    def __post_init__(self):
        """初始化後建立空的 stopped_bus DataFrame，使用全域定義的 schedule_index 作為索引。"""
        self.stopped_bus = pd.DataFrame(
            {"data": [[] for _ in range(len(schedule_index))]},
            index=schedule_index,
        )


@dataclass
class Route:
    """
    公車路線資料類別。

    Attributes:
        stops (list[Stop]):  路線包含的站點列表，依序排列。
        _delta_time_table (dict[Stop, dict[Stop, int]]): 站點間的預估時間差 (分鐘)，用於計算站點抵達時間，初始化後設定。
    """

    stops: list[Stop]
    _delta_time_table: dict[Stop, dict[Stop, int]] = field(
        default_factory=dict, init=False
    )

    def __post_init__(self):
        """初始化後設定預設的站點間時間差。 注意：此處使用全域定義的 Stop 物件作為鍵。"""
        self._delta_time_table = {
            stops["M1"]: {stops["M2"]: 1},
            stops["M2"]: {stops["M1"]: 1, stops["M3"]: 1, stops["M4"]: 3},
            stops["M3"]: {stops["M2"]: 1, stops["M4"]: 2, stops["M6"]: 1},
            stops["M4"]: {stops["M2"]: 3, stops["M3"]: 2, stops["M5"]: 2},
            stops["M5"]: {stops["M4"]: 2, stops["M7"]: 1, stops["S1"]: 15},
            stops["M6"]: {stops["M2"]: 2, stops["M3"]: 1, stops["M7"]: 2},
            stops["M7"]: {stops["M5"]: 1, stops["M6"]: 2},
            stops["S1"]: {stops["M5"]: 15},
        }

    def gen_accumulated_time(self) -> list[int]:
        """
        計算路線上每個站點的累積時間。

        Returns:
            list[int]: 包含每個站點累積時間的列表，第一個站點時間為 0 分鐘。
        """
        acc_times = [0]
        for i in range(len(self.stops) - 1):
            acc_times.append(
                acc_times[i] + self._delta_time_table[self.stops[i]][self.stops[i + 1]]
            )
        return acc_times


# 站點資料
M1 = Stop("北校門口", "North Main Gate", "24.79589", "120.99633")
M2 = Stop("綜二館", "General Building II", "24.794176", "120.99376")
M3 = Stop("楓林小徑", "Maple Path", "24.791388889", "120.991388889")
M4 = Stop("人社院/生科館", "CHSS/CLS Building", "24.79", "120.990277778")
M5 = Stop("台積館", "TSMC Building", "24.78695", "120.9884")
M6 = Stop(
    "奕園停車場", "Yi Pavilion Parking Lot", "24.788284441920126", "120.99246131713849"
)
M7 = Stop("南門停車場", "South Gate Parking Lot", "24.7859395", "120.9901396")
S1 = Stop(
    "南大校區校門口右側(食品路校牆邊)",
    "The right side of NandaCampus front gate(Shipin Road)",
    "24.79438267696105",
    "120.965382976675",
)
stops: dict[str, Stop] = {
    "M1": M1,
    "M2": M2,
    "M3": M3,
    "M4": M4,
    "M5": M5,
    "M6": M6,
    "M7": M7,
    "S1": S1,
}
stop_name_mapping: dict[str, Stop] = {stop.name: stop for stop in stops.values()}

# 清大路網圖 (單位：分鐘)
#                        M4
#     1      1     2/         \2    15
# M1 --- M2 --- M3              M5 ---- S1
#                 1\          /1
#                   M6 --- M7

# 紅線
red_M1_M5 = Route([M1, M2, M3, M4, M5])  # 北校門往台積館
red_M5_M1 = Route([M5, M7, M6, M2, M1])  # 台積館往北校門
red_M2_M5 = Route([M2, M3, M4, M5])  # 綜二館往台積館
red_M5_M2 = Route([M5, M7, M6, M2])  # 台積館往綜二館

# 綠線
green_M1_M5 = Route([M1, M2, M3, M6, M7, M5])  # 北校門往台積館
green_M5_M1 = Route([M5, M4, M2, M1])  # 台積館往北校門
green_M2_M5 = Route([M2, M3, M6, M7, M5])  # 綜二館往台積館
green_M5_M2 = Route([M5, M4, M2])  # 台積館往綜二館

# 校區區間車
nanda_M1_S1 = Route([M1, M2, M4, M5, S1])  # 南大校區校門口右側往北校門
nanda_S1_M1 = Route([S1, M5, M4, M2, M1])  # 北校門往南大校區校門口右側


class Buses:
    """
    校園公車時刻表管理類別。

    提供校園公車時刻表的資料獲取、處理和查詢功能。
    資料來源為清華大學提供的 JSON 格式公車時刻表 API。
    支援校本部公車和南大校區區間車時刻表，並提供站點資訊查詢。

    資料會定期從遠端 JSON 端點更新，以確保資訊的即時性。

    Attributes:
        raw_schedule_data (pd.DataFrame): 原始公車時刻表資料，以 DataFrame 儲存，索引為多層索引 (BUS_TYPE, BUS_DAY, BUS_DIRECTION)。
        detailed_schedule_data (pd.DataFrame): 詳細公車時刻表資料，包含停靠站點時間等詳細資訊。
        info_data (pd.DataFrame): 公車路線資訊，例如首末班車時間、發車間隔等。
        _last_updated_time (Optional[float]): 上次資料更新時間戳記，用於 TTL 快取機制。
    """

    def __init__(self) -> None:
        """
        初始化 Buses 類別。

        初始化各項資料 DataFrame，並載入公車時刻表資料。
        若快取資料過期或尚未初始化，則會從遠端端點重新獲取資料。
        """
        self.raw_schedule_data = pd.DataFrame(
            {"data": [[] for _ in range(len(schedule_index))]}, index=schedule_index
        )
        self.detailed_schedule_data = pd.DataFrame(
            {"data": [[] for _ in range(len(schedule_index))]}, index=schedule_index
        )
        self.info_data = pd.DataFrame(
            {
                "data": [
                    []
                    for _ in range(len(BUS_ROUTE_TYPE_WITHOUT_ALL) * len(BUS_DIRECTION))
                ]
            },
            index=pd.MultiIndex.from_product(
                [BUS_ROUTE_TYPE_WITHOUT_ALL, BUS_DIRECTION]
            ),
        )
        self.last_commit_hash = None

        self._res_json: dict = {}  # 儲存原始 JSON 回應資料
        self._start_from_gen_2_bus_info: list[str] = []  # 記錄從綜二館發車的班次資訊
        self._last_updated_time: Optional[float] = None  # 上次資料更新時間戳記

    async def _process_bus_data(self) -> None:
        """
        處理從 JSON API 獲取的公車時刻表資料。

        此方法負責解析 JSON 資料，並將資料填入 `info_data`、`raw_schedule_data` 和 `detailed_schedule_data` 等 DataFrame 中。
        同時會呼叫 `gen_bus_detailed_schedule_and_update_stops_data` 方法產生詳細時刻表並更新站點資訊。
        """
        self._populate_info_data()
        self._populate_raw_schedule_data()
        self._add_fields_to_raw_schedule_data()
        await self.gen_bus_detailed_schedule_and_update_stops_data()

    def _populate_info_data(self) -> None:
        """
        將原始 JSON 資料填入 info_data DataFrame。

        遍歷 BUS_TYPE_WITHOUT_ALL, BUS_DIRECTION 的所有組合，從 JSON 資料中提取對應的路線資訊，
        並存儲到 info_data DataFrame 中。
        """
        for route_type, direction in product(BUS_ROUTE_TYPE_WITHOUT_ALL, BUS_DIRECTION):
            info_key = f"toward{self.transform_toward_name(route_type, direction)}Info"
            info_data = self._res_json.get(info_key, {})
            self.info_data.loc[(route_type, direction), "data"] = [info_data]

    def _populate_raw_schedule_data(self) -> None:
        """
        將原始 JSON 資料填入 raw_schedule_data DataFrame。

        遍歷 BUS_TYPE_WITHOUT_ALL, BUS_DAY, BUS_DIRECTION 的所有組合，從 JSON 資料中提取對應的時刻表資料，
        並存儲到 raw_schedule_data DataFrame 中。
        """
        for route_type, day, direction in product(
            BUS_ROUTE_TYPE_WITHOUT_ALL, BUS_DAY, BUS_DIRECTION
        ):
            schedule_key = f"{day}BusScheduleToward{self.transform_toward_name(route_type, direction)}"
            schedule_data = self._res_json.get(schedule_key, [])
            self.raw_schedule_data.loc[(route_type, day, direction), "data"] = (
                schedule_data
            )
        gen_the_all_field(self.raw_schedule_data, ["time"])  # 合併與排序 'all' 欄位

    def _classify_bus_type(
        self, route_type: str, day: str, description: str
    ) -> schemas.buses.BusType:
        """
        根據公車路線類型、時刻表註解和日期分類，判斷公車類型。

        Args:
            route_type (str): 公車路線類型，'main' 代表校本部公車，'nanda' 代表南大區間車。
            day (str): 日期類型，'weekday' 代表平日，'weekend' 代表假日。
            description (str): 時刻表註解，用於判斷公車類型。

        Returns:
            schemas.buses.BusType: 公車類型，包含 'route_83', 'large-sized_bus', 'middle-sized_bus'。
        """
        # 優先判斷是否為 83 路
        if route_type == "nanda" and "83" in description:
            return schemas.buses.BusType.route_83

        # 校內公車註解中包含 "大" 或南大平日，為大型巴士
        elif (route_type == "main" and "大" in description) or (
            route_type == "nanda" and day == "weekday"
        ):
            return schemas.buses.BusType.large_sized_bus

        # 其他校內和校區區間公車為中型巴士
        else:
            return schemas.buses.BusType.middle_sized_bus

    def _add_fields_to_raw_schedule_data(self) -> None:
        """
        將 raw_schedule_data DataFrame 中的時刻表資料添加額外的欄位。
        - 加入 `bus_type` 欄位。
        - 若 `route_type` 為 "nanda"，同時新增 `dep_stop`。
        """
        for route_type, day, direction in product(
            BUS_ROUTE_TYPE_WITHOUT_ALL, BUS_DAY, BUS_DIRECTION
        ):
            for item in self.raw_schedule_data.loc[
                (route_type, day, direction), "data"
            ]:
                # 新增 bus_type 欄位
                item["bus_type"] = self._classify_bus_type(
                    route_type, day, item["description"]
                )

                # nanda 新增 dep_stop 欄位
                if route_type == "nanda":
                    item["dep_stop"] = "校門" if direction == "up" else "南大"

    def transform_toward_name(
        self, route: Literal["main", "nanda"], direction: Literal["up", "down"]
    ) -> str:
        """
        轉換路線與方向名稱為 JSON 資料中使用的名稱格式。

        Args:
            route (Literal["main", "nanda"]): 路線類型，'main' 代表校本部公車，'nanda' 代表南大區間車。
            direction (Literal["up", "down"]): 行車方向，'up' 代表往特定方向 (如台積館、南大校區)，'down' 代表往反方向 (如校門口、校本部)。

        Returns:
            str: 轉換後的名稱字串，用於在 JSON 資料中查找對應的鍵。
        """
        trans_list = {
            ("main", "up"): "TSMCBuilding",
            ("main", "down"): "MainGate",
            ("nanda", "up"): "SouthCampus",
            ("nanda", "down"): "MainCampus",
        }
        return trans_list[(route, direction)]

    def _get_route_data(self, route_type: Literal["main", "nanda"]) -> dict:
        """
        獲取特定路線類型的公車相關資料。

        Args:
            route_type (Literal["main", "nanda"]): 路線類型，'main' 代表校本部公車，'nanda' 代表南大區間車。

        Returns:
            dict: 包含指定路線類型的公車資訊和時刻表的字典。
        """
        # 根據路線類型設置不同的向位名稱
        if route_type == "main":
            up_name = "TSMC_building"
            down_name = "main_gate"
        else:  # route_type == "nanda"
            up_name = "south_campus"
            down_name = "main_campus"

        return {
            f"toward_{up_name}_info": self.info_data.loc[(route_type, "up"), "data"][0],
            f"weekday_bus_schedule_toward_{up_name}": self.raw_schedule_data.loc[
                (route_type, "weekday", "up"), "data"
            ],
            f"weekend_bus_schedule_toward_{up_name}": self.raw_schedule_data.loc[
                (route_type, "weekend", "up"), "data"
            ],
            f"toward_{down_name}_info": self.info_data.loc[
                (route_type, "down"), "data"
            ][0],
            f"weekday_bus_schedule_toward_{down_name}": self.raw_schedule_data.loc[
                (route_type, "weekday", "down"), "data"
            ],
            f"weekend_bus_schedule_toward_{down_name}": self.raw_schedule_data.loc[
                (route_type, "weekend", "down"), "data"
            ],
        }

    def get_main_data(self) -> dict:
        """
        取得校本部公車相關資料。

        Returns:
            dict: 包含校本部公車路線資訊和時刻表的字典，鍵值包含 'toward_TSMC_building_info', 'weekday_bus_schedule_toward_TSMC_building' 等。
        """
        return self._get_route_data("main")

    def get_nanda_data(self) -> dict:
        """
        取得南大校區區間車相關資料。

        Returns:
            dict: 包含南大校區區間車路線資訊和時刻表的字典，鍵值包含 'toward_south_campus_info', 'weekday_bus_schedule_toward_south_campus' 等。
        """
        return self._get_route_data("nanda")

    def _reset_stop_data(self) -> None:
        """重新初始化所有 Stop 物件的 stopped_bus DataFrame，用於更新站點公車資訊。"""
        for stop in stops.values():
            stop.stopped_bus = pd.DataFrame(
                {"data": [[] for _ in range(len(schedule_index))]},
                index=schedule_index,
            )

    async def update_data(self) -> None:
        """更新公車時刻表資料，包含從 API 獲取最新資料並重新處理。"""
        # asyncio.gather(self._init_task)  # 等待初始化任務完成

        res_commit_hash, self._res_json = await nthudata.get(
            "buses.json"
        )  # 直接更新 _res_json，後續處理會使用最新的 json 資料

        if (
            self._res_json and res_commit_hash != self.last_commit_hash
        ):  # 只有成功獲取資料且資料不一致時才需要重新處理
            await self._process_bus_data()
            self.last_commit_hash = res_commit_hash
        self._start_from_gen_2_bus_info.clear()  # 清空從綜二館發車的班次資訊快取

    def _add_on_time(self, start_time: str, time_delta: int) -> str:
        """
        在指定時間字串上增加分鐘數。

        Args:
            start_time (str): 開始時間字串，格式為 '%H:%M'。
            time_delta (int): 要增加的分鐘數。

        Returns:
            str: 增加分鐘數後的時間字串，格式為 '%H:%M'。
        """
        st = datetime.strptime(start_time, "%H:%M") + timedelta(minutes=time_delta)
        return st.strftime("%H:%M")

    def _find_stop_from_str(self, stop_str: str) -> Optional[Stop]:
        """
        根據站點名稱字串查找對應的 Stop 物件。

        Args:
            stop_str (str): 站點名稱字串 (中文)。

        Returns:
            Optional[Stop]: 若找到對應的 Stop 物件則返回，否則返回 None。
        """
        return stop_name_mapping.get(stop_str)

    def _route_selector(
        self, dep_stop: str, line: str, from_gen_2: bool = False
    ) -> Optional[Route]:
        """
        根據出發站點、路線代碼和是否從綜二館發車，選擇對應的 Route 物件。

        Args:
            dep_stop (str): 出發站點名稱字串 (如 "台積館", "校門", "綜二")。
            line (str): 路線代碼 (如 "red", "green")。
            from_gen_2 (bool): 是否從綜二館發車，僅對校本部公車紅綠線有效。

        Returns:
            Optional[Route]: 若找到對應的 Route 物件則返回，否則返回 None。
        """
        dep_stop, line = dep_stop.strip(), line.strip()
        stops_lines_map: dict[tuple, Route] = {
            ("台積館", "red", True): red_M5_M2,
            ("台積館", "red", False): red_M5_M1,
            ("台積館", "green", True): green_M5_M2,
            ("台積館", "green", False): green_M5_M1,
            ("校門", "red"): red_M1_M5,
            ("綜二", "red"): red_M2_M5,
            ("校門", "green"): green_M1_M5,
            ("綜二", "green"): green_M2_M5,
        }
        key = (
            (dep_stop, line) if "台積" not in dep_stop else (dep_stop, line, from_gen_2)
        )
        return stops_lines_map.get(key)

    def _gen_detailed_bus_schedule(
        self,
        bus_schedule: list[dict],
        *,
        route_type: Literal["main", "nanda"] = "main",
        day: Literal["weekday", "weekend"] = "weekday",
        direction: Literal["up", "down"] = "up",
    ) -> list[dict]:
        """
        產生詳細的公車時刻表，包含每個班次在每個站點的抵達時間。

        Args:
            bus_schedule (list[dict]): 原始公車時刻表資料，包含發車時間、路線等資訊。
            route_type (Literal["main", "nanda"]): 公車類型，'main' 為校本部, 'nanda' 為南大區間車，預設為 'main'。
            day (Literal["weekday", "weekend"]):  平日或假日時刻表，預設為 'weekday'。
            direction (Literal["up", "down"]): 行車方向，預設為 'up'。

        Returns:
            list[dict]: 詳細公車時刻表列表，每個元素為一個字典，包含班次資訊和每個停靠站點的抵達時間。
        """
        detailed_schedules: list[dict] = []
        for bus in bus_schedule:
            detailed_bus_schedule = self._process_single_bus_schedule(
                bus, route_type=route_type, day=day, direction=direction
            )
            detailed_schedules.append(detailed_bus_schedule)
        return detailed_schedules

    def _process_single_bus_schedule(
        self,
        bus: dict,
        *,
        route_type: Literal["main", "nanda"],
        day: Literal["weekday", "weekend"],
        direction: Literal["up", "down"],
    ) -> dict:
        """
        處理單個公車班次的時刻表，生成包含停靠站點時間的詳細資訊。

        Args:
            bus (dict): 單個公車班次的原始時刻表資料。
            route_type (Literal["main", "nanda"]): 公車類型。
            day (Literal["weekday", "weekend"]): 平日或假日。
            direction (Literal["up", "down"]): 行車方向。

        Returns:
            dict: 包含單個公車班次詳細時刻表的字典，包含班次資訊和每個停靠站點的抵達時間。
        """
        temp_bus: dict[str, Any] = {"dep_info": bus, "stops_time": []}
        route: Optional[Route] = self._select_bus_route(
            bus, route_type=route_type, day=day, direction=direction
        )

        if route:
            self._populate_stop_times_and_update_stop_data(
                temp_bus,
                bus,
                route,
                route_type=route_type,
                day=day,
                direction=direction,
            )
        return temp_bus

    def _select_bus_route(
        self,
        bus: dict,
        *,
        route_type: Literal["main", "nanda"],
        day: Literal["weekday", "weekend"],
        direction: Literal["up", "down"],
    ) -> Optional[Route]:
        """
        根據公車資訊選擇對應的公車路線。

        Args:
            bus (dict): 單個公車班次的原始時刻表資料。
            route_type (Literal["main", "nanda"]): 公車類型。
            direction (Literal["up", "down"]): 行車方向。

        Returns:
            Optional[Route]: 若找到對應的 Route 物件則返回，否則返回 None。
        """
        if route_type == "main":
            return self._select_main_bus_route(bus)
        elif route_type == "nanda":
            return self._select_nanda_bus_route(direction)
        return None

    def _select_main_bus_route(self, bus: dict) -> Optional[Route]:
        """
        選擇校本部公車路線。

        根據公車資訊中的出發站點和路線代碼，以及是否從綜二館發車的資訊，選擇對應的 Route 物件。

        Args:
            bus (dict): 單個校本部公車班次的原始時刻表資料。

        Returns:
            Optional[Route]: 若找到對應的 Route 物件則返回，否則返回 None。
        """
        dep_stop = bus.get("dep_stop", "")
        line = bus.get("line", "")
        dep_from_gen_2 = self._is_departure_from_gen_2(bus, line)
        if "綜二" in dep_stop:
            self._record_gen_2_departure_time(bus, line)
        return self._route_selector(dep_stop, line, dep_from_gen_2)

    def _select_nanda_bus_route(
        self, direction: Literal["up", "down"]
    ) -> Optional[Route]:
        """
        選擇南大校區區間車路線。

        根據行車方向選擇對應的南大校區區間車 Route 物件。

        Args:
            direction (Literal["up", "down"]): 行車方向。

        Returns:
            Optional[Route]: 若找到對應的 Route 物件則返回，否則返回 None。
        """
        return nanda_M1_S1 if direction == "up" else nanda_S1_M1

    def _is_departure_from_gen_2(self, bus: dict, line: str) -> bool:
        """
        判斷公車是否從綜二館發車。

        檢查公車資訊中的時間和路線代碼是否在記錄的從綜二館發車的班次資訊列表中。

        Args:
            bus (dict): 單個公車班次的原始時刻表資料。
            line (str): 路線代碼。

        Returns:
            bool: 若公車從綜二館發車則返回 True，否則返回 False。
        """
        bus_identifier = bus["time"] + line
        return bus_identifier in self._start_from_gen_2_bus_info or (
            "0" + bus["time"] + line in self._start_from_gen_2_bus_info
        )

    def _record_gen_2_departure_time(self, bus: dict, line: str) -> None:
        """
        記錄從綜二館發車的班次資訊。

        將從綜二館發車的班次時間和路線代碼加入到 `_start_from_gen_2_bus_info` 列表中，用於後續判斷是否從綜二館發車。
        並在發車時間上增加 7 分鐘，作為後續站點時間計算的基準。

        Args:
            bus (dict): 單個公車班次的原始時刻表資料。
            line (str): 路線代碼。
        """
        self._start_from_gen_2_bus_info.append(self._add_on_time(bus["time"], 7) + line)

    def _populate_stop_times_and_update_stop_data(
        self,
        temp_bus: dict,
        bus: dict,
        route: Route,
        *,
        route_type: Literal["main", "nanda"],
        day: Literal["weekday", "weekend"],
        direction: Literal["up", "down"],
    ) -> None:
        """
        填充公車班次在每個站點的抵達時間，並更新站點的停靠公車資料。

        Args:
            temp_bus (dict): 儲存單個公車班次詳細時刻表的字典。
            bus (dict): 單個公車班次的原始時刻表資料。
            route (Route): 公車路線物件。
            route_type (Literal["main", "nanda"]): 公車類型。
            day (Literal["weekday", "weekend"]): 平日或假日。
            direction (Literal["up", "down"]): 行車方向。
        """
        acc_times = route.gen_accumulated_time()
        for idx, stop in enumerate(route.stops):
            arrive_time = self._add_on_time(bus["time"], acc_times[idx])
            self._update_stop_stopped_bus_data(
                stop,
                bus,
                arrive_time,
                route_type=route_type,
                day=day,
                direction=direction,
            )
            temp_bus["stops_time"].append(
                {
                    "stop_name": stop.name,
                    "time": arrive_time,
                }
            )

    def _update_stop_stopped_bus_data(
        self,
        stop: Stop,
        bus: dict,
        arrive_time: str,
        *,
        route_type: Literal["main", "nanda"],
        day: Literal["weekday", "weekend"],
        direction: Literal["up", "down"],
    ) -> None:
        """
        更新單個站點的停靠公車資料。

        將公車班次資訊和抵達時間添加到指定站點的 `stopped_bus` DataFrame 中。

        Args:
            stop (Stop): 公車站點物件。
            bus (dict): 單個公車班次的原始時刻表資料。
            arrive_time (str): 公車班次在該站點的抵達時間。
            route_type (Literal["main", "nanda"]): 公車類型。
            day (Literal["weekday", "weekend"]): 平日或假日。
            direction (Literal["up", "down"]): 行車方向。
        """
        stop_obj = self._find_stop_from_str(stop.name)
        if stop_obj:
            stop_obj.stopped_bus.loc[(route_type, day, direction), "data"].append(
                {
                    "bus_info": bus,
                    "arrive_time": arrive_time,
                }
            )

    async def gen_bus_detailed_schedule_and_update_stops_data(self) -> None:
        """
        產生詳細公車時刻表並更新各站點的停靠公車資訊。

        此方法會呼叫 `_update_data()` 更新資料，並同時更新 `detailed_schedule_data` 與各 `Stop` 物件的 `stopped_bus` 屬性。
        產生詳細時刻表的過程會計算每個班次在每個站點的預計抵達時間。
        """
        self._reset_stop_data()  # 清空站點的停靠公車資料，準備重新計算
        # await self.update_data()  # 又被移回來了：Ｄ ~~資料更新移至 _process_bus_data 中處理~~

        for route_type, day, direction in product(
            BUS_ROUTE_TYPE_WITHOUT_ALL, BUS_DAY_WITHOUT_ALL, BUS_DIRECTION
        ):
            self.detailed_schedule_data.loc[(route_type, day, direction), "data"] = (
                self._gen_detailed_bus_schedule(
                    self.raw_schedule_data.loc[(route_type, day, direction), "data"],
                    route_type=route_type,
                    day=day,
                    direction=direction,
                )
            )

        gen_the_all_field(
            self.detailed_schedule_data, ["dep_info", "time"]
        )  # 合併與排序 detailed_schedule_data 的 'all' 欄位
        for stop in stops.values():
            gen_the_all_field(
                stop.stopped_bus, ["arrive_time"]
            )  # 合併與排序每個站點 stopped_bus 的 'all' 欄位

    def gen_bus_stops_info(self) -> list[dict]:
        """
        產生公車站點資訊列表。

        Returns:
            list[dict]: 包含所有公車站點資訊的列表，每個元素為一個字典，包含 'stop_name', 'stop_name_en', 'latitude', 'longitude' 鍵值。
        """
        return [
            {
                "stop_name": stop.name,
                "stop_name_en": stop.name_en,
                "latitude": stop.latitude,
                "longitude": stop.longitude,
            }
            for stop in stops.values()
        ]
