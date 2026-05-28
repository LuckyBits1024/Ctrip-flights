import gzip
import json
import os
import time
from datetime import datetime as dt
from urllib.parse import urlencode

import pandas as pd
from selenium.common.exceptions import NoSuchWindowException, WebDriverException

import ctrip_flights_scraper_V3 as browser_scraper
import ctrip_international_api as international_api
import flight_query_config as flight_config


BATCH_SEARCH_PATH = "/international/search/api/search/batchSearch"
BROWSER_API_COLUMNS = international_api.INTERNATIONAL_API_COLUMNS


def route_cache_file(run_day):
    return os.path.join(".codex", f"browser_api_route_cache_{run_day}.json")


def status_file(run_day):
    return os.path.join(".codex", f"browser_api_job_status_{run_day}.json")


def write_status(path, payload):
    if not path:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)


def task_key(task):
    return "|".join(task)


def load_route_cache(cache_file):
    if not cache_file or not os.path.exists(cache_file):
        return {}
    with open(cache_file, "r", encoding="utf-8") as f:
        return json.load(f)


def save_route_cache(cache_file, cache):
    if not cache_file:
        return
    os.makedirs(os.path.dirname(cache_file), exist_ok=True)
    with open(cache_file, "w", encoding="utf-8") as f:
        json.dump(cache, f, ensure_ascii=False, indent=2)


def build_search_url(departure_code, arrival_code, depart_date):
    query = urlencode(
        {
            "depdate": depart_date,
            "cabin": "y_s",
            "adult": 1,
            "child": 0,
            "infant": 0,
        }
    )
    return (
        "https://flights.ctrip.com/international/search/"
        f"oneway-{departure_code.lower()}-{arrival_code.lower()}?{query}"
    )


def reset_network_capture(driver):
    try:
        del driver.requests
    except AttributeError:
        pass


def decode_response_json(request):
    body = request.response.body
    encoding = request.response.headers.get("Content-Encoding", "")
    if "gzip" in encoding.lower():
        body = gzip.decompress(body)
    return json.loads(body.decode("utf-8"))


def request_body_json(request):
    if not request.body:
        return {}
    return json.loads(request.body.decode("utf-8"))


def request_matches_route(request, departure_code, arrival_code, depart_date):
    if not request.response or BATCH_SEARCH_PATH not in request.url:
        return False
    try:
        payload = request_body_json(request)
    except Exception:
        return False
    segments = payload.get("flightSegments") or []
    if not segments:
        return False
    segment = segments[0]
    return (
        segment.get("departureCityCode") == departure_code
        and segment.get("arrivalCityCode") == arrival_code
        and segment.get("departureDate") == depart_date
    )


def parse_browser_batch_response(response):
    parsed = international_api.parse_oneway_response(response)
    data = response.get("data") or {}
    context = data.get("context") or {}
    if context.get("searchId"):
        parsed["search_id"] = context["searchId"]
    return parsed


def browser_session_lost(error):
    text = f"{type(error).__name__}: {error}"
    return (
        isinstance(error, NoSuchWindowException)
        or "no such window" in text
        or "web view not found" in text
        or "invalid session id" in text
    )


def fetch_oneway_price_with_browser(
    driver,
    departure_city,
    arrival_city,
    depart_date,
    timeout=45,
    auth_retry_wait=15,
    auth_retry_count=1,
    auth_quiet_seconds=8,
    log=print,
):
    departure_code = international_api.fetch_city_code(departure_city)
    arrival_code = international_api.fetch_city_code(arrival_city)
    url = build_search_url(departure_code, arrival_code, depart_date)

    reset_network_capture(driver)
    log(f"打开国际机票页面：{departure_city}->{arrival_city} {depart_date} {url}")
    driver.get(url)

    deadline = time.time() + timeout
    saw_auth_code = False
    saw_login = False
    saw_batch_search = False
    last_reason = "未捕获到 batchSearch 响应"
    last_matched_response_at = None
    parsed_request_ids = set()

    while time.time() < deadline:
        for request in reversed(driver.requests):
            if id(request) in parsed_request_ids:
                continue
            if not request_matches_route(request, departure_code, arrival_code, depart_date):
                continue
            parsed_request_ids.add(id(request))
            saw_batch_search = True
            try:
                response = decode_response_json(request)
            except Exception as e:
                last_reason = f"batchSearch 响应解析失败：{type(e).__name__}: {e}"
                continue

            last_matched_response_at = time.time()
            parsed = parse_browser_batch_response(response)
            parsed["route_code"] = f"{departure_code}->{arrival_code}"
            if parsed["status"] == "成功":
                return parsed
            if parsed["status"] == "API安全验证":
                saw_auth_code = True
            if parsed["status"] == "API需要登录":
                saw_login = True
            last_reason = parsed.get("reason") or parsed["status"]

        if (
            saw_auth_code
            and last_matched_response_at
            and time.time() - last_matched_response_at >= auth_quiet_seconds
        ):
            break
        time.sleep(1)

    if saw_auth_code:
        if auth_retry_count > 0:
            log(
                "检测到 batchSearch 安全验证，"
                f"等待 {auth_retry_wait}s 后刷新重试一次：{departure_city}->{arrival_city} {depart_date}"
            )
            time.sleep(auth_retry_wait)
            return fetch_oneway_price_with_browser(
                driver,
                departure_city,
                arrival_city,
                depart_date,
                timeout=timeout,
                auth_retry_wait=auth_retry_wait,
                auth_retry_count=auth_retry_count - 1,
                auth_quiet_seconds=auth_quiet_seconds,
                log=log,
            )
        status = "API安全验证"
        last_reason = "真实页面 batchSearch 只返回 showAuthCode"
    elif saw_login:
        status = "API需要登录"
        last_reason = "真实页面 batchSearch 只返回 needUserLogin"
    elif saw_batch_search:
        status = "API无价格"
    else:
        status = "API超时"
    return {
        "status": status,
        "price": None,
        "flight_info": "",
        "route_code": f"{departure_code}->{arrival_code}",
        "reason": last_reason,
    }


def fetch_route_date_prices_with_browser(
    tasks,
    timeout=45,
    request_interval=5.0,
    max_requests=0,
    profile_dir=None,
    cache_file=None,
    status_path=None,
    max_consecutive_auth=5,
    auth_cooldown=180,
    log=print,
):
    if profile_dir:
        browser_scraper.CHROME_PROFILE_DIR = os.path.abspath(profile_dir)

    cache = load_route_cache(cache_file)
    results = {
        task: cache[task_key(task)]
        for task in tasks
        if task_key(task) in cache
    }
    pending_tasks = [
        task
        for task in tasks
        if results.get(task, {}).get("status") != "成功"
    ]
    selected_tasks = pending_tasks[:max_requests] if max_requests else pending_tasks
    skipped_count = len(tasks) - len(pending_tasks)
    write_status(
        status_path,
        {
            "state": "running",
            "updated_at": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": len(tasks),
            "cached_success": skipped_count,
            "pending_tasks": len(pending_tasks),
            "selected_tasks": len(selected_tasks),
            "completed_this_run": 0,
            "success_total": skipped_count,
        },
    )
    if skipped_count:
        log(f"已从缓存读取成功单程查询 {skipped_count} 个，本轮跳过这些单程日期")
    if not selected_tasks:
        log("没有需要新增查询的单程日期，直接用缓存生成汇总")
        return results

    driver = browser_scraper.init_driver()
    consecutive_auth_count = 0
    try:
        for index, (departure_city, arrival_city, depart_date) in enumerate(selected_tasks, start=1):
            log(f"开始浏览器 API 查询 {index}/{len(selected_tasks)}：{departure_city}->{arrival_city} {depart_date}")
            try:
                result = fetch_oneway_price_with_browser(
                    driver,
                    departure_city,
                    arrival_city,
                    depart_date,
                    timeout=timeout,
                    log=log,
                )
            except Exception as e:
                if browser_session_lost(e):
                    log("浏览器窗口已丢失，重开 Chrome 后重试当前单程日期")
                    try:
                        driver.quit()
                    except WebDriverException:
                        pass
                    driver = browser_scraper.init_driver()
                    try:
                        result = fetch_oneway_price_with_browser(
                            driver,
                            departure_city,
                            arrival_city,
                            depart_date,
                            timeout=timeout,
                            log=log,
                        )
                    except Exception as retry_error:
                        result = {
                            "status": "浏览器API异常",
                            "price": None,
                            "flight_info": "",
                            "route_code": "",
                            "reason": f"{type(retry_error).__name__}: {retry_error}",
                        }
                else:
                    result = {
                        "status": "浏览器API异常",
                        "price": None,
                        "flight_info": "",
                        "route_code": "",
                        "reason": f"{type(e).__name__}: {e}",
                    }
            task = (departure_city, arrival_city, depart_date)
            results[task] = result
            cache[task_key(task)] = result
            save_route_cache(cache_file, cache)
            success_total = sum(
                1
                for task_item in tasks
                if results.get(task_item, {}).get("status") == "成功"
            )
            write_status(
                status_path,
                {
                    "state": "running",
                    "updated_at": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                    "total_tasks": len(tasks),
                    "cached_success": skipped_count,
                    "pending_tasks": len(pending_tasks),
                    "selected_tasks": len(selected_tasks),
                    "completed_this_run": index,
                    "success_total": success_total,
                    "last_task": {
                        "departure_city": departure_city,
                        "arrival_city": arrival_city,
                        "depart_date": depart_date,
                        "status": result["status"],
                        "price": result.get("price"),
                        "reason": result.get("reason"),
                    },
                },
            )
            log(
                "完成浏览器 API 查询 "
                f"{index}/{len(selected_tasks)}：{result['status']} "
                f"{result.get('route_code', '')} {result.get('reason', '')}"
            )
            if result["status"] == "API安全验证":
                consecutive_auth_count += 1
            else:
                consecutive_auth_count = 0
            if max_consecutive_auth and consecutive_auth_count >= max_consecutive_auth:
                log(
                    f"连续 {consecutive_auth_count} 个查询返回安全验证，"
                    f"冷却 {auth_cooldown}s 后重开 Chrome 继续"
                )
                write_status(
                    status_path,
                    {
                        "state": "security_cooldown",
                        "updated_at": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
                        "total_tasks": len(tasks),
                        "selected_tasks": len(selected_tasks),
                        "completed_this_run": index,
                        "success_total": success_total,
                        "auth_cooldown_seconds": auth_cooldown,
                        "last_task": {
                            "departure_city": departure_city,
                            "arrival_city": arrival_city,
                            "depart_date": depart_date,
                            "status": result["status"],
                            "reason": result.get("reason"),
                        },
                    },
                )
                time.sleep(auth_cooldown)
                try:
                    driver.quit()
                except WebDriverException:
                    pass
                driver = browser_scraper.init_driver()
                consecutive_auth_count = 0
            if index < len(selected_tasks) and request_interval > 0:
                time.sleep(request_interval)
    finally:
        driver.quit()
    return results


def build_open_jaw_rows(pairs, date_pairs, route_results):
    rows = international_api.build_open_jaw_rows(pairs, date_pairs, route_results)
    for row in rows:
        row["查询方式"] = "真实浏览器 batchSearch API"
        if row["状态"] == "成功":
            row["价格说明"] = "真实浏览器 batchSearch API 两段单程最低成人票价+税费相加"
    return rows


def write_results(rows, run_day):
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{flight_config.begin_date}_to_{flight_config.end_date}",
        run_day,
        "international_browser_api",
    )
    os.makedirs(files_dir, exist_ok=True)
    output_file = os.path.join(files_dir, f"{flight_config.origin_city}-欧洲开口程浏览器API汇总.csv")
    frame = pd.DataFrame(rows, columns=BROWSER_API_COLUMNS)
    frame = international_api.sort_results(frame)
    frame.to_csv(output_file, encoding="UTF-8", index=False)
    return output_file


def run_browser_api_job(
    cities,
    run_day,
    timeout=45,
    request_interval=5.0,
    max_requests=0,
    profile_dir=None,
    max_consecutive_auth=5,
    auth_cooldown=180,
    log=print,
):
    date_pairs = flight_config.generate_round_trip_dates(
        flight_config.begin_date,
        flight_config.end_date,
        flight_config.min_stay_days,
        flight_config.days_interval,
    )
    pairs = international_api.build_open_jaw_pairs(cities)
    tasks = international_api.route_date_tasks(pairs, date_pairs)
    log(
        "浏览器 API 任务准备完成："
        f"城市 {len(cities)} 个，开口程组合 {len(pairs)} 组，日期组合 {len(date_pairs)} 组，"
        f"去重单程日期查询 {len(tasks)} 个"
    )
    route_results = fetch_route_date_prices_with_browser(
        tasks,
        timeout=timeout,
        request_interval=request_interval,
        max_requests=max_requests,
        profile_dir=profile_dir,
        cache_file=route_cache_file(run_day),
        status_path=status_file(run_day),
        max_consecutive_auth=max_consecutive_auth,
        auth_cooldown=auth_cooldown,
        log=log,
    )
    rows = build_open_jaw_rows(pairs, date_pairs, route_results)
    output_file = write_results(rows, run_day)
    write_status(
        status_file(run_day),
        {
            "state": "completed",
            "updated_at": dt.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_tasks": len(tasks),
            "success_total": sum(
                1
                for task in tasks
                if route_results.get(task, {}).get("status") == "成功"
            ),
            "output_file": output_file,
        },
    )
    log(f"浏览器 API 汇总文件已生成：{output_file}")
    return output_file
