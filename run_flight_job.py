import argparse
import json
import os
import time
from datetime import datetime as dt

import pandas as pd

import ctrip_flights_scraper_V3 as scraper


STATUS_FILE = os.path.join(".codex", "flight_job_status.json")
LOG_FILE = os.path.join(".codex", "flight_job.log")
ERROR_SCREENSHOT_FILE = os.path.join(".codex", "flight_job_last_error.png")


def now_text():
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def log(message):
    line = f"{now_text()} {message}"
    print(line, flush=True)
    os.makedirs(".codex", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def is_success_result(path):
    if not os.path.exists(path):
        return False
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log(f"读取结果文件失败：{path}，{type(e).__name__}: {e}")
        return False
    if df.empty or "状态" not in df.columns or "往返含税价" not in df.columns:
        return False
    has_success = (df["状态"] == "成功").any()
    prices = df["往返含税价"].dropna().astype(str)
    has_price = any(price.strip() and price.strip().lower() != "nan" for price in prices)
    return has_success and has_price


def is_business_no_result(path):
    if not os.path.exists(path):
        return False
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log(f"读取结果文件失败：{path}，{type(e).__name__}: {e}")
        return False
    if df.empty or "状态" not in df.columns:
        return False
    statuses = df["状态"].dropna().astype(str)
    return any(status == "无航班结果" for status in statuses)


def is_completed_result(path):
    return is_success_result(path) or is_business_no_result(path)


def write_open_jaw_group_files(pairs):
    group_files = []
    for outbound_destination, return_departure_city in pairs:
        group_file = scraper.write_open_jaw_group_results(outbound_destination, return_departure_city)
        if group_file:
            group_files.append(group_file)
            log(f"开口程汇总文件已生成：{group_file}")
    return group_files


def build_roundtrip_tasks(cities, force=False):
    date_pairs = scraper.generate_round_trip_dates(
        scraper.begin_date,
        scraper.end_date,
        scraper.min_stay_days,
        scraper.days_interval,
    )
    tasks = []
    for city in cities:
        route = [scraper.origin_city, city]
        for depart_date, return_date in date_pairs:
            output_file = scraper.result_file_path(route, depart_date, return_date)
            if force or not is_completed_result(output_file):
                tasks.append(
                    {
                        "city": city,
                        "route": route,
                        "depart_date": depart_date,
                        "return_date": return_date,
                        "output_file": output_file,
                    }
                )
            else:
                scraper.append_result_file(output_file)
    return tasks


def build_open_jaw_tasks(pairs, force=False):
    date_pairs = scraper.generate_round_trip_dates(
        scraper.begin_date,
        scraper.end_date,
        scraper.min_stay_days,
        scraper.days_interval,
    )
    tasks = []
    for outbound_destination, return_departure_city in pairs:
        route = [scraper.origin_city, outbound_destination]
        for depart_date, return_date in date_pairs:
            output_file = scraper.open_jaw_raw_result_file_path(
                outbound_destination,
                return_departure_city,
                depart_date,
                return_date,
            )
            if force or not is_completed_result(output_file):
                tasks.append(
                    {
                        "mode": "open_jaw",
                        "city": outbound_destination,
                        "return_departure_city": return_departure_city,
                        "route": route,
                        "depart_date": depart_date,
                        "return_date": return_date,
                        "output_file": output_file,
                    }
                )
            else:
                scraper.append_result_file(output_file)
    return tasks


def write_status(status):
    os.makedirs(".codex", exist_ok=True)
    status["updated_at"] = dt.now().isoformat(timespec="seconds")
    with open(STATUS_FILE, "w", encoding="utf-8") as f:
        json.dump(status, f, ensure_ascii=False, indent=2)


def write_failure(fetcher, reason):
    fetcher.records = [fetcher.build_no_result_record(reason)]
    fetcher.write_roundtrip_data()


def restart_fetcher(fetcher):
    try:
        fetcher.driver.quit()
    except Exception as e:
        log(f"重启浏览器前关闭旧 driver 失败：{type(e).__name__}: {e}")

    driver = scraper.init_driver()
    return driver, scraper.DataFetcher(driver)


def parse_args():
    parser = argparse.ArgumentParser(description="低频执行携程往返机票查询任务队列")
    parser.add_argument("--cities", nargs="+", default=["巴黎"], help="目的地城市列表")
    parser.add_argument("--all-cities", action="store_true", help="查询脚本配置中的全部欧洲目的地")
    parser.add_argument(
        "--open-jaw",
        nargs=2,
        action="append",
        metavar=("OUTBOUND_DESTINATION", "RETURN_DEPARTURE_CITY"),
        help="开口程城市对，例如：--open-jaw 巴黎 米兰 表示上海->巴黎、米兰->上海",
    )
    parser.add_argument("--interval", type=int, default=120, help="每组查询后的等待秒数")
    parser.add_argument("--max-wait", type=int, default=60, help="首页控件等待秒数")
    parser.add_argument("--max-search-wait", type=int, default=180, help="结果页等待秒数")
    parser.add_argument("--max-consecutive-failures", type=int, default=2, help="连续失败达到该值后停止")
    parser.add_argument("--limit", type=int, default=0, help="本次最多执行的任务数，0 表示不限制")
    parser.add_argument("--force", action="store_true", help="忽略已有成功结果，重新执行全部任务")
    return parser.parse_args()


def run_flight_job(args):
    run_day = dt.now().strftime("%Y-%m-%d")
    scraper.set_result_run_day(run_day)
    cities = scraper.destination_citys if args.all_cities else args.cities
    open_jaw_pairs = args.open_jaw or []

    scraper.crawl_interval = args.interval
    scraper.max_wait_time = args.max_wait
    scraper.max_search_wait_time = args.max_search_wait
    scraper.max_retry_time = 1
    scraper.send_email_after_run = False

    if open_jaw_pairs:
        tasks = build_open_jaw_tasks(open_jaw_pairs, force=args.force)
        run_label = [f"{pair[0]}<-{pair[1]}" for pair in open_jaw_pairs]
        run_mode = "open_jaw"
    else:
        tasks = build_roundtrip_tasks(cities, force=args.force)
        run_label = cities
        run_mode = "roundtrip"
    if args.limit:
        tasks = tasks[:args.limit]
    status = {
        "started_at": dt.now().isoformat(timespec="seconds"),
        "mode": run_mode,
        "cities": run_label,
        "total_pending_at_start": len(tasks),
        "completed_this_run": 0,
        "failed_this_run": 0,
        "stopped": False,
        "stop_reason": "",
    }
    write_status(status)
    log(f"任务启动：模式 {run_mode}，城市 {run_label}，待执行 {len(tasks)} 组，间隔 {args.interval}s")

    if not tasks:
        if run_mode == "roundtrip":
            combined_file = scraper.write_combined_results(scraper.result_files)
            if combined_file:
                log(f"无待执行任务，汇总文件已生成：{combined_file}")
        else:
            group_files = write_open_jaw_group_files(open_jaw_pairs)
            if not group_files:
                log("无待执行开口程任务，未找到可汇总的 raw 文件")
        return

    driver = scraper.init_driver()
    fetcher = scraper.DataFetcher(driver)
    consecutive_failures = 0

    try:
        for index, task in enumerate(tasks, start=1):
            technical_failure = False
            fetcher.city = task["route"]
            fetcher.date = task["depart_date"]
            fetcher.return_date = task["return_date"]
            fetcher.query_mode = task.get("mode", "roundtrip")
            fetcher.return_departure_city = task.get("return_departure_city")
            fetcher.captcha_detected = False

            if fetcher.query_mode == "open_jaw":
                log(
                    f"开始 {index}/{len(tasks)}：{task['route'][0]}-{task['route'][1]} / "
                    f"{task['return_departure_city']}-{task['route'][0]} "
                    f"{task['depart_date']} -> {task['return_date']}"
                )
            else:
                log(
                    f"开始 {index}/{len(tasks)}：{task['route'][0]}-{task['route'][1]} "
                    f"{task['depart_date']} -> {task['return_date']}"
                )

            try:
                fetcher.get_page(1)
            except Exception as e:
                reason = f"runner 查询异常：{type(e).__name__}, {str(e).split('Stacktrace:')[0].strip()}"
                log(reason)
                try:
                    os.makedirs(".codex", exist_ok=True)
                    fetcher.driver.save_screenshot(ERROR_SCREENSHOT_FILE)
                    log(f"错误截图已保存：{ERROR_SCREENSHOT_FILE}")
                except Exception as screenshot_error:
                    log(f"错误截图保存失败：{type(screenshot_error).__name__}: {screenshot_error}")
                write_failure(fetcher, reason)
                technical_failure = True

            if fetcher.captcha_detected:
                reason = "验证码或风控触发，runner 停止执行"
                write_failure(fetcher, reason)
                status["stopped"] = True
                status["stop_reason"] = reason
                write_status(status)
                log(reason)
                break

            if is_success_result(task["output_file"]):
                group_ready = True
                if fetcher.query_mode == "open_jaw":
                    try:
                        group_file = scraper.write_open_jaw_group_results(task["city"], task["return_departure_city"])
                    except Exception as e:
                        group_file = None
                        log(f"open_jaw group 汇总失败：{type(e).__name__}: {e}")
                    if not group_file:
                        group_ready = False

                if group_ready:
                    consecutive_failures = 0
                    status["completed_this_run"] += 1
                    scraper.append_result_file(task["output_file"])
                    log(f"成功：{task['output_file']}")
                else:
                    consecutive_failures += 1
                    status["failed_this_run"] += 1
                    technical_failure = True
                    log(f"失败：open_jaw group 汇总未生成，连续失败 {consecutive_failures}/{args.max_consecutive_failures}")
            elif is_business_no_result(task["output_file"]):
                consecutive_failures = 0
                status["completed_this_run"] += 1
                scraper.append_result_file(task["output_file"])
                log(f"无航班结果：{task['output_file']}")
            else:
                consecutive_failures += 1
                status["failed_this_run"] += 1
                if not os.path.exists(task["output_file"]):
                    write_failure(fetcher, "runner 未生成结果文件")
                technical_failure = True
                log(f"失败：连续失败 {consecutive_failures}/{args.max_consecutive_failures}")

            write_status(status)

            if consecutive_failures >= args.max_consecutive_failures:
                reason = f"连续失败达到 {args.max_consecutive_failures} 次，runner 停止执行"
                status["stopped"] = True
                status["stop_reason"] = reason
                write_status(status)
                log(reason)
                break

            if technical_failure:
                log("本组技术失败，重启浏览器会话后继续下一组")
                driver, fetcher = restart_fetcher(fetcher)

            if index < len(tasks):
                log(f"等待 {args.interval} 秒后继续下一组")
                time.sleep(args.interval)
    finally:
        driver.quit()

    if run_mode == "roundtrip":
        combined_file = scraper.write_combined_results(scraper.result_files)
        if combined_file:
            log(f"汇总文件已生成：{combined_file}")
    else:
        write_open_jaw_group_files(open_jaw_pairs)
    log("任务结束")


def main():
    args = parse_args()
    run_flight_job(args)


if __name__ == "__main__":
    main()
