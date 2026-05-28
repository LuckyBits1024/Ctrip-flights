import hashlib
import json
import os
import re
import time
from datetime import datetime as dt
from html import unescape
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

import pandas as pd

import flight_query_config as flight_config


POI_SEARCH_URL = "https://flights.ctrip.com/international/search/api/poi/search"
BATCH_SEARCH_URL = "https://flights.ctrip.com/international/search/api/search/batchSearch?v="
COOKIES_FILE = "cookies.json"

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

INTERNATIONAL_API_COLUMNS = [
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
    "去程航班信息",
    "回程航班信息",
    "去程城市代码",
    "返程城市代码",
    "价格说明",
]


def load_cookie_header(cookies_file=COOKIES_FILE):
    if not os.path.exists(cookies_file):
        return ""
    with open(cookies_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    cookies = data.get("manual_login", [])
    return "; ".join(
        f"{cookie.get('name')}={cookie.get('value')}"
        for cookie in cookies
        if cookie.get("name") and cookie.get("value")
    )


def cookie_header_to_dict(cookie_header):
    cookies = {}
    if not cookie_header:
        return cookies
    for item in cookie_header.split(";"):
        item = item.strip()
        if not item or "=" not in item:
            continue
        name, value = item.split("=", 1)
        cookies[name] = value
    return cookies


def dict_to_cookie_header(cookies):
    return "; ".join(f"{name}={value}" for name, value in cookies.items() if name and value)


def merge_cookie_header(cookie_header, updates):
    cookies = cookie_header_to_dict(cookie_header)
    cookies.update({name: value for name, value in updates.items() if name and value})
    return dict_to_cookie_header(cookies)


def extract_set_cookie_headers(response):
    updates = {}
    for header in response.headers.get_all("Set-Cookie", []):
        first_part = header.split(";", 1)[0]
        if "=" not in first_part:
            continue
        name, value = first_part.split("=", 1)
        updates[name] = value
    return updates


def extract_document_cookies(html):
    updates = {}
    for raw_cookie in re.findall(r"document\.cookie\s*=\s*['\"]([^'\"]+)['\"]", html):
        first_part = raw_cookie.split(";", 1)[0]
        if "=" not in first_part:
            continue
        name, value = first_part.split("=", 1)
        updates[name] = value
    return updates


def request_json(url, headers=None, data=None, timeout=20):
    request = Request(url, data=data, headers=headers or {})
    with urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8"))


def fetch_city_code(city, timeout=20):
    if city in CITY_CODES:
        return CITY_CODES[city]

    url = f"{POI_SEARCH_URL}?{urlencode({'key': city})}"
    payload = request_json(
        url,
        headers={
            "Accept": "application/json, text/plain, */*",
            "User-Agent": "Mozilla/5.0",
            "Referer": "https://flights.ctrip.com/international/search/",
        },
        timeout=timeout,
    )
    items = payload.get("Data") or []
    if not items:
        raise ValueError(f"未找到城市代码：{city}")
    return items[0]["Code"]


def extract_global_search_criteria(html):
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json">(.*?)</script>',
        html,
    )
    if not match:
        raise ValueError("页面中未找到 __NEXT_DATA__")
    data = json.loads(unescape(match.group(1)))
    return data["props"]["pageProps"]["renderData"]["GlobalSearchCriteria"]


def fetch_global_search_criteria(departure_code, arrival_code, depart_date, cookie_header="", timeout=20):
    path = f"oneway-{departure_code.lower()}-{arrival_code.lower()}"
    query = urlencode(
        {
            "depdate": depart_date,
            "cabin": "y_s",
            "adult": 1,
            "child": 0,
            "infant": 0,
        }
    )
    url = f"https://flights.ctrip.com/international/search/{path}?{query}"
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://flights.ctrip.com/international/search/",
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    request = Request(url, headers=headers)
    with urlopen(request, timeout=timeout) as response:
        html = response.read().decode("utf-8")
        cookie_updates = extract_set_cookie_headers(response)
    cookie_updates.update(extract_document_cookies(html))
    updated_cookie_header = merge_cookie_header(cookie_header, cookie_updates)
    return url, extract_global_search_criteria(html), updated_cookie_header, cookie_updates


def generate_sign(criteria):
    text = ""
    for segment in criteria["flightSegments"]:
        text += segment["departureCityCode"]
        text += segment["arrivalCityCode"]
        text += segment["departureDate"]
    return hashlib.md5((criteria["transactionID"] + text).encode("utf-8")).hexdigest()


def request_batch_search(criteria, referer_url, cookie_header="", timeout=30):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"{referer_url}&directflight=",
        "Content-Type": "application/json;charset=utf-8",
        "sign": generate_sign(criteria),
        "transactionid": criteria["transactionID"],
    }
    if cookie_header:
        headers["Cookie"] = cookie_header
    body = json.dumps(criteria, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return request_json(BATCH_SEARCH_URL, headers=headers, data=body, timeout=timeout)


def cookie_names(cookie_header):
    if not cookie_header:
        return []
    names = []
    for item in cookie_header.split(";"):
        item = item.strip()
        if not item:
            continue
        names.append(item.split("=", 1)[0])
    return names


def debug_print_payload(title, payload, log=print):
    log(f"========== {title} ==========")
    log(json.dumps(payload, ensure_ascii=False, indent=2))


def request_batch_search_debug(criteria, referer_url, cookie_header="", timeout=30, log=print):
    headers = {
        "User-Agent": "Mozilla/5.0",
        "Referer": f"{referer_url}&directflight=",
        "Content-Type": "application/json;charset=utf-8",
        "sign": generate_sign(criteria),
        "transactionid": criteria["transactionID"],
    }
    if cookie_header:
        headers["Cookie"] = cookie_header

    body_text = json.dumps(criteria, ensure_ascii=False, separators=(",", ":"))
    debug_print_payload(
        "batchSearch 请求信息",
        {
            "url": BATCH_SEARCH_URL,
            "headers": {
                key: value
                for key, value in headers.items()
                if key != "Cookie"
            },
            "cookie_names": cookie_names(cookie_header),
            "body": criteria,
        },
        log=log,
    )
    response = request_json(
        BATCH_SEARCH_URL,
        headers=headers,
        data=body_text.encode("utf-8"),
        timeout=timeout,
    )
    debug_print_payload("batchSearch 完整响应", response, log=log)
    return response


def extract_first_price(itinerary):
    price_list = itinerary.get("priceList") or []
    if not price_list:
        return None
    price = price_list[0]
    adult_price = price.get("adultPrice") or 0
    adult_tax = price.get("adultTax") or 0
    return int(adult_price + adult_tax)


def select_lowest_itinerary(itineraries):
    priced_items = []
    for itinerary in itineraries:
        price = extract_first_price(itinerary)
        if price is not None:
            priced_items.append((price, itinerary))
    if not priced_items:
        return None, None
    return min(priced_items, key=lambda item: item[0])


def describe_itinerary(itinerary):
    segments = itinerary.get("flightSegments") or []
    if not segments:
        return ""
    flights = segments[0].get("flightList") or []
    parts = []
    for flight in flights:
        parts.append(
            f"{flight.get('flightNo', '')} "
            f"{flight.get('departureCityName', '')}{flight.get('departureDateTime', '')}"
            f"->{flight.get('arrivalCityName', '')}{flight.get('arrivalDateTime', '')}"
        )
    return " | ".join(parts)


def parse_oneway_response(response):
    data = response.get("data") or {}
    context = data.get("context") or {}
    if context.get("showAuthCode") is True:
        return {"status": "API安全验证", "price": None, "flight_info": "", "reason": "batchSearch 返回 showAuthCode"}
    if data.get("needUserLogin") is True:
        return {"status": "API需要登录", "price": None, "flight_info": "", "reason": "batchSearch 返回 needUserLogin"}

    itineraries = data.get("flightItineraryList") or []
    if not itineraries:
        return {"status": "API无价格", "price": None, "flight_info": "", "reason": "batchSearch 未返回 flightItineraryList"}

    price, itinerary = select_lowest_itinerary(itineraries)
    if price is None:
        return {"status": "API无价格", "price": None, "flight_info": "", "reason": "航班列表无 priceList"}
    return {
        "status": "成功",
        "price": price,
        "flight_info": describe_itinerary(itinerary),
        "reason": "batchSearch 最低成人票价+税费",
    }


def fetch_oneway_price(departure_city, arrival_city, depart_date, cookie_header="", timeout=30, debug_print=False, log=print):
    departure_code = fetch_city_code(departure_city, timeout=timeout)
    arrival_code = fetch_city_code(arrival_city, timeout=timeout)
    referer_url, criteria, updated_cookie_header, cookie_updates = fetch_global_search_criteria(
        departure_code,
        arrival_code,
        depart_date,
        cookie_header=cookie_header,
        timeout=timeout,
    )
    if debug_print:
        debug_print_payload(
            "国际搜索页表单数据",
            {
                "departure_city": departure_city,
                "arrival_city": arrival_city,
                "depart_date": depart_date,
                "referer_url": referer_url,
                "criteria": criteria,
                "page_cookie_updates": sorted(cookie_updates.keys()),
                "batch_cookie_names": cookie_names(updated_cookie_header),
                "sign_source": criteria["transactionID"]
                + "".join(
                    segment["departureCityCode"] + segment["arrivalCityCode"] + segment["departureDate"]
                    for segment in criteria["flightSegments"]
                ),
                "sign": generate_sign(criteria),
            },
            log=log,
        )
        response = request_batch_search_debug(
            criteria,
            referer_url,
            cookie_header=updated_cookie_header,
            timeout=timeout,
            log=log,
        )
    else:
        response = request_batch_search(
            criteria,
            referer_url,
            cookie_header=updated_cookie_header,
            timeout=timeout,
        )
    parsed = parse_oneway_response(response)
    parsed["route_code"] = f"{departure_code}->{arrival_code}"
    return parsed


def build_open_jaw_pairs(cities):
    return [
        [outbound_destination, return_departure_city]
        for outbound_destination in cities
        for return_departure_city in cities
        if outbound_destination != return_departure_city
    ]


def route_date_tasks(pairs, date_pairs):
    tasks = []
    seen = set()
    for outbound_destination, return_departure_city in pairs:
        for depart_date, return_date in date_pairs:
            outbound_key = (flight_config.origin_city, outbound_destination, depart_date)
            return_key = (return_departure_city, flight_config.origin_city, return_date)
            if outbound_key not in seen:
                seen.add(outbound_key)
                tasks.append(outbound_key)
            if return_key not in seen:
                seen.add(return_key)
                tasks.append(return_key)
    return tasks


def fetch_route_date_prices(tasks, cookie_header="", timeout=30, request_interval=2.0, max_requests=0, debug_print=False, log=print):
    results = {}
    selected_tasks = tasks[:max_requests] if max_requests else tasks
    for index, (departure_city, arrival_city, depart_date) in enumerate(selected_tasks, start=1):
        log(f"开始国际 API 查询 {index}/{len(selected_tasks)}：{departure_city}->{arrival_city} {depart_date}")
        try:
            result = fetch_oneway_price(
                departure_city,
                arrival_city,
                depart_date,
                cookie_header=cookie_header,
                timeout=timeout,
                debug_print=debug_print,
                log=log,
            )
        except Exception as e:
            result = {
                "status": "API请求异常",
                "price": None,
                "flight_info": "",
                "route_code": "",
                "reason": f"{type(e).__name__}: {e}",
            }
        results[(departure_city, arrival_city, depart_date)] = result
        log(f"完成国际 API 查询 {index}/{len(selected_tasks)}：{result['status']} {result.get('route_code', '')} {result.get('reason', '')}")
        if index < len(selected_tasks) and request_interval > 0:
            time.sleep(request_interval)
    return results


def build_open_jaw_rows(pairs, date_pairs, route_results):
    rows = []
    query_date = dt.now().strftime("%Y-%m-%d")
    for outbound_destination, return_departure_city in pairs:
        for depart_date, return_date in date_pairs:
            outbound = route_results.get((flight_config.origin_city, outbound_destination, depart_date))
            inbound = route_results.get((return_departure_city, flight_config.origin_city, return_date))
            stay_days = (
                dt.strptime(return_date, "%Y-%m-%d")
                - dt.strptime(depart_date, "%Y-%m-%d")
            ).days

            if outbound and inbound and outbound["status"] == "成功" and inbound["status"] == "成功":
                status = "成功"
                total_price = outbound["price"] + inbound["price"]
                price_note = "国际 batchSearch API 两段单程最低成人票价+税费相加"
            else:
                status_parts = []
                if outbound:
                    status_parts.append(f"去程{outbound['status']}")
                else:
                    status_parts.append("去程未查询")
                if inbound:
                    status_parts.append(f"回程{inbound['status']}")
                else:
                    status_parts.append("回程未查询")
                status = "；".join(status_parts)
                total_price = ""
                price_note = "；".join(
                    part
                    for part in [
                        outbound.get("reason") if outbound else "去程未查询",
                        inbound.get("reason") if inbound else "回程未查询",
                    ]
                    if part
                )

            rows.append(
                {
                    "状态": status,
                    "查询日期": query_date,
                    "查询方式": "international batchSearch API",
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
                    "去程API价格": outbound.get("price", "") if outbound else "",
                    "回程API价格": inbound.get("price", "") if inbound else "",
                    "去程航班信息": outbound.get("flight_info", "") if outbound else "",
                    "回程航班信息": inbound.get("flight_info", "") if inbound else "",
                    "去程城市代码": outbound.get("route_code", "") if outbound else "",
                    "返程城市代码": inbound.get("route_code", "") if inbound else "",
                    "价格说明": price_note,
                }
            )
    return rows


def sort_results(frame):
    frame["_sort_price"] = pd.to_numeric(frame["开口程含税价"], errors="coerce")
    frame = frame.sort_values("_sort_price", ascending=True, na_position="last")
    return frame.drop(columns=["_sort_price"])


def write_results(rows, run_day):
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{flight_config.begin_date}_to_{flight_config.end_date}",
        run_day,
        "international_api",
    )
    os.makedirs(files_dir, exist_ok=True)
    output_file = os.path.join(files_dir, f"{flight_config.origin_city}-欧洲开口程国际API汇总.csv")
    frame = pd.DataFrame(rows, columns=INTERNATIONAL_API_COLUMNS)
    frame = sort_results(frame)
    frame.to_csv(output_file, encoding="UTF-8", index=False)
    return output_file


def run_international_api_job(
    cities,
    run_day,
    use_cookies=True,
    timeout=30,
    request_interval=2.0,
    max_requests=0,
    debug_print=False,
    log=print,
):
    date_pairs = flight_config.generate_round_trip_dates(
        flight_config.begin_date,
        flight_config.end_date,
        flight_config.min_stay_days,
        flight_config.days_interval,
    )
    pairs = build_open_jaw_pairs(cities)
    tasks = route_date_tasks(pairs, date_pairs)
    cookie_header = load_cookie_header() if use_cookies else ""
    log(f"国际 API 任务准备完成：城市 {len(cities)} 个，开口程组合 {len(pairs)} 组，日期组合 {len(date_pairs)} 组，去重单程日期查询 {len(tasks)} 个")
    route_results = fetch_route_date_prices(
        tasks,
        cookie_header=cookie_header,
        timeout=timeout,
        request_interval=request_interval,
        max_requests=max_requests,
        debug_print=debug_print,
        log=log,
    )
    rows = build_open_jaw_rows(pairs, date_pairs, route_results)
    output_file = write_results(rows, run_day)
    log(f"国际 API 汇总文件已生成：{output_file}")
    return output_file
