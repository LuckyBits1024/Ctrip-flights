import json
import os
import time
from datetime import datetime as dt
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import pandas as pd

import flight_query_config as flight_config


LOWEST_PRICE_API_URL = "https://flights.ctrip.com/itinerary/api/12808/lowestPrice"
ORIGIN_CITY_CODE = "SHA"

CITY_CODES = {
    "上海": "SHA",
    "巴黎": "PAR",
    "法兰克福": "FRA",
    "慕尼黑": "MUC",
    "柏林": "BER",
    "杜塞尔多夫": "DUS",
    "汉堡": "HAM",
    "尼斯": "NCE",
    "里昂": "LYS",
    "马赛": "MRS",
    "罗马": "ROM",
    "米兰": "MIL",
    "威尼斯": "VCE",
    "佛罗伦萨": "FLR",
    "那不勒斯": "NAP",
    "苏黎世": "ZRH",
    "日内瓦": "GVA",
    "巴塞尔": "EAP",
}

API_RESULT_COLUMNS = [
    "状态",
    "查询日期",
    "查询方式",
    "开口程组合",
    "出发城市",
    "目的城市",
    "去程出发城市",
    "去程到达城市",
    "返程出发城市",
    "返程到达城市",
    "去程出发日期",
    "回程出发日期",
    "停留天数",
    "往返含税价",
    "开口程含税价",
    "去程API价格",
    "回程API价格",
    "去程城市代码",
    "返程城市代码",
    "价格说明",
]


def resolve_city_code(city):
    if city not in CITY_CODES:
        raise ValueError(f"缺少城市代码映射：{city}")
    return CITY_CODES[city]


def parse_price_calendar(items):
    prices = {}
    if not items:
        return prices

    for item in items:
        for date_key, price in item.items():
            try:
                date_text = dt.strptime(str(date_key), "%Y%m%d").strftime("%Y-%m-%d")
                prices[date_text] = int(price)
            except (TypeError, ValueError):
                continue
    return prices


def fetch_lowest_price_calendar(departure_code, arrival_code, direct=False, timeout=20):
    params = {
        "flightWay": "Oneway",
        "dcity": departure_code,
        "acity": arrival_code,
        "direct": str(direct).lower(),
        "army": "false",
    }
    url = f"{LOWEST_PRICE_API_URL}?{urlencode(params)}"
    request = Request(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://flights.ctrip.com/",
        },
    )
    with urlopen(request, timeout=timeout) as response:
        payload = json.loads(response.read().decode("utf-8"))

    data = payload.get("data") or {}
    return parse_price_calendar(data.get("oneWayPrice"))


def generate_date_pairs(begin_date, end_date, min_stay_days, days_interval):
    return flight_config.generate_round_trip_dates(begin_date, end_date, min_stay_days, days_interval)


def build_open_jaw_pairs(cities, include_same_city=False):
    return [
        [outbound_destination, return_departure_city]
        for outbound_destination in cities
        for return_departure_city in cities
        if include_same_city or outbound_destination != return_departure_city
    ]


def unique_routes_for_pairs(pairs):
    routes = []
    seen = set()
    for outbound_destination, return_departure_city in pairs:
        outbound_route = (ORIGIN_CITY_CODE, resolve_city_code(outbound_destination))
        inbound_route = (resolve_city_code(return_departure_city), ORIGIN_CITY_CODE)
        for route in [outbound_route, inbound_route]:
            if route in seen:
                continue
            seen.add(route)
            routes.append(route)
    return routes


def fetch_route_calendars(routes, direct=False, timeout=20, request_interval=2.0, log=print):
    calendars = {}
    for index, route in enumerate(routes, start=1):
        departure_code, arrival_code = route
        log(f"开始 API 查询 {index}/{len(routes)}：{departure_code}->{arrival_code}")
        calendars[route] = fetch_lowest_price_calendar(
            departure_code,
            arrival_code,
            direct=direct,
            timeout=timeout,
        )
        log(f"完成 API 查询 {index}/{len(routes)}：{departure_code}->{arrival_code}，返回 {len(calendars[route])} 个日期价格")
        if index < len(routes) and request_interval > 0:
            time.sleep(request_interval)
    return calendars


def build_api_rows(pairs, date_pairs, calendars):
    rows = []
    query_date = dt.now().strftime("%Y-%m-%d")
    for outbound_destination, return_departure_city in pairs:
        outbound_code = resolve_city_code(outbound_destination)
        return_departure_code = resolve_city_code(return_departure_city)
        outbound_prices = calendars.get((ORIGIN_CITY_CODE, outbound_code), {})
        return_prices = calendars.get((return_departure_code, ORIGIN_CITY_CODE), {})

        for depart_date, return_date in date_pairs:
            outbound_price = outbound_prices.get(depart_date)
            return_price = return_prices.get(return_date)
            stay_days = (
                dt.strptime(return_date, "%Y-%m-%d")
                - dt.strptime(depart_date, "%Y-%m-%d")
            ).days
            has_price = outbound_price is not None and return_price is not None
            total_price = outbound_price + return_price if has_price else ""
            price_note = (
                "lowestPrice API 两段单程最低价相加，非携程多程页面含税总价"
                if has_price
                else "lowestPrice API 未返回该开口程日期组合的两段单程价格"
            )
            rows.append(
                {
                    "状态": "成功" if has_price else "接口无价格",
                    "查询日期": query_date,
                    "查询方式": "lowestPrice API",
                    "开口程组合": f"{flight_config.origin_city}-{outbound_destination}__{return_departure_city}-{flight_config.origin_city}",
                    "出发城市": flight_config.origin_city,
                    "目的城市": outbound_destination,
                    "去程出发城市": flight_config.origin_city,
                    "去程到达城市": outbound_destination,
                    "返程出发城市": return_departure_city,
                    "返程到达城市": flight_config.origin_city,
                    "去程出发日期": depart_date,
                    "回程出发日期": return_date,
                    "停留天数": stay_days,
                    "往返含税价": total_price,
                    "开口程含税价": total_price,
                    "去程API价格": outbound_price if outbound_price is not None else "",
                    "回程API价格": return_price if return_price is not None else "",
                    "去程城市代码": f"{ORIGIN_CITY_CODE}->{outbound_code}",
                    "返程城市代码": f"{return_departure_code}->{ORIGIN_CITY_CODE}",
                    "价格说明": price_note,
                }
            )
    return rows


def sort_api_results(frame):
    frame["_sort_price"] = pd.to_numeric(frame["开口程含税价"], errors="coerce")
    frame = frame.sort_values("_sort_price", ascending=True, na_position="last")
    return frame.drop(columns=["_sort_price"])


def write_api_results(rows, run_day, filename=None):
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{flight_config.begin_date}_to_{flight_config.end_date}",
        run_day,
        "api_lowest_price",
    )
    os.makedirs(files_dir, exist_ok=True)
    output_file = filename or os.path.join(files_dir, f"{flight_config.origin_city}-欧洲开口程API低价汇总.csv")
    frame = pd.DataFrame(rows, columns=API_RESULT_COLUMNS)
    frame = sort_api_results(frame)
    frame.to_csv(output_file, encoding="UTF-8", index=False)
    return output_file


def run_api_lowest_price_job(
    cities,
    run_day,
    include_same_city=False,
    direct=False,
    timeout=20,
    request_interval=2.0,
    log=print,
):
    pairs = build_open_jaw_pairs(cities, include_same_city=include_same_city)
    date_pairs = generate_date_pairs(
        flight_config.begin_date,
        flight_config.end_date,
        flight_config.min_stay_days,
        flight_config.days_interval,
    )
    routes = unique_routes_for_pairs(pairs)
    log(f"API 任务准备完成：城市 {len(cities)} 个，开口程组合 {len(pairs)} 组，日期组合 {len(date_pairs)} 组，API 航线 {len(routes)} 条")
    calendars = fetch_route_calendars(
        routes,
        direct=direct,
        timeout=timeout,
        request_interval=request_interval,
        log=log,
    )
    rows = build_api_rows(pairs, date_pairs, calendars)
    output_file = write_api_results(rows, run_day)
    log(f"API 汇总文件已生成：{output_file}")
    return output_file
