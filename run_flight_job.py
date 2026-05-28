import argparse
import json
import os
import random
import re
import time
from datetime import datetime as dt

import pandas as pd
from selenium.common.exceptions import NoSuchWindowException

import ctrip_flights_scraper_V3 as scraper


STATUS_FILE = os.path.join(".codex", "flight_job_status.json")
LOG_FILE = os.path.join(".codex", "flight_job.log")
ERROR_SCREENSHOT_FILE = os.path.join(".codex", "flight_job_last_error.png")


def safe_worker_id(worker_id):
    return re.sub(r"[^0-9A-Za-z_-]+", "_", worker_id).strip("_")


def configure_worker_files(worker_id):
    global STATUS_FILE, LOG_FILE, ERROR_SCREENSHOT_FILE
    worker_id = safe_worker_id(worker_id)
    if not worker_id or worker_id == "main":
        STATUS_FILE = os.path.join(".codex", "flight_job_status.json")
        LOG_FILE = os.path.join(".codex", "flight_job.log")
        ERROR_SCREENSHOT_FILE = os.path.join(".codex", "flight_job_last_error.png")
        return "main"

    STATUS_FILE = os.path.join(".codex", f"flight_job_status_{worker_id}.json")
    LOG_FILE = os.path.join(".codex", f"flight_job_{worker_id}.log")
    ERROR_SCREENSHOT_FILE = os.path.join(".codex", f"flight_job_last_error_{worker_id}.png")
    return worker_id


def default_profile_dir(worker_id):
    if worker_id == "main":
        return scraper.CHROME_PROFILE_DIR
    return os.path.abspath(os.path.join(".codex", f"chrome-profile-{worker_id}"))


def is_browser_session_lost_error(error):
    text = str(error)
    return (
        isinstance(error, NoSuchWindowException)
        or "target window already closed" in text
        or "web view not found" in text
        or "invalid session id" in text
    )


def now_text():
    return time.strftime("%Y-%m-%d_%H-%M-%S")


def log(message):
    line = f"{now_text()} {message}"
    print(line, flush=True)
    os.makedirs(".codex", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def rows_for_date(df, depart_date, return_date):
    if depart_date is None or return_date is None:
        return df
    return df[
        (df["去程出发日期"].astype(str) == depart_date)
        & (df["回程出发日期"].astype(str) == return_date)
    ]


def is_success_result(path, depart_date=None, return_date=None):
    if not os.path.exists(path):
        return False
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log(f"读取结果文件失败：{path}，{type(e).__name__}: {e}")
        return False
    if df.empty or "状态" not in df.columns or "往返含税价" not in df.columns:
        return False
    df = rows_for_date(df, depart_date, return_date)
    has_success = (df["状态"] == "成功").any()
    prices = df["往返含税价"].dropna().astype(str)
    has_price = any(price.strip() and price.strip().lower() != "nan" for price in prices)
    return has_success and has_price


def is_business_no_result(path, depart_date=None, return_date=None):
    if not os.path.exists(path):
        return False
    try:
        df = pd.read_csv(path)
    except Exception as e:
        log(f"读取结果文件失败：{path}，{type(e).__name__}: {e}")
        return False
    if df.empty or "状态" not in df.columns:
        return False
    df = rows_for_date(df, depart_date, return_date)
    statuses = df["状态"].dropna().astype(str)
    return any(status == "无航班结果" for status in statuses)


def has_result_for_date(path, depart_date, return_date):
    if not os.path.exists(path):
        return False
    df = pd.read_csv(path)
    if df.empty or "去程出发日期" not in df.columns or "回程出发日期" not in df.columns:
        return False
    return not rows_for_date(df, depart_date, return_date).empty


def is_completed_result(path, depart_date, return_date):
    return is_success_result(path, depart_date, return_date) or is_business_no_result(path, depart_date, return_date)


def write_open_jaw_group_files(pairs):
    group_files = []
    for outbound_destination, return_departure_city in pairs:
        group_file = scraper.write_open_jaw_group_results(outbound_destination, return_departure_city)
        if group_file:
            group_files.append(group_file)
            log(f"开口程汇总文件已生成：{group_file}")
    return group_files


def count_date_pairs():
    return len(
        scraper.generate_round_trip_dates(
            scraper.begin_date,
            scraper.end_date,
            scraper.min_stay_days,
            scraper.days_interval,
        )
    )


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
            if force or not is_completed_result(output_file, depart_date, return_date):
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


def build_all_open_jaw_pairs(cities):
    return [
        [outbound_destination, return_departure_city]
        for outbound_destination in cities
        for return_departure_city in cities
        if outbound_destination != return_departure_city
    ]


def unique_open_jaw_pairs(pairs):
    unique_pairs = []
    seen = set()
    for outbound_destination, return_departure_city in pairs:
        key = (outbound_destination, return_departure_city)
        if key in seen:
            continue
        seen.add(key)
        unique_pairs.append([outbound_destination, return_departure_city])
    return unique_pairs


def shard_sequence(items, shard_index, shard_count):
    if shard_count < 1:
        raise ValueError("--shard-count 必须大于等于 1")
    if shard_index < 0 or shard_index >= shard_count:
        raise ValueError("--shard-index 必须在 0 到 --shard-count-1 之间")
    return [item for index, item in enumerate(items) if index % shard_count == shard_index]


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
            output_file = scraper.open_jaw_group_result_file_path(
                outbound_destination,
                return_departure_city,
            )
            if force or not is_completed_result(output_file, depart_date, return_date):
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


def run_query_once(fetcher):
    fetcher.browser_session_lost = False
    fetcher.browser_restart_required = False
    try:
        page_loaded = fetcher.get_page(1)
        try:
            fetcher.driver.current_window_handle
        except Exception as session_error:
            if is_browser_session_lost_error(session_error):
                fetcher.browser_session_lost = True
                log(f"查询后检测到浏览器会话丢失：{type(session_error).__name__}: {session_error}")
        try:
            if fetcher.has_login_modal():
                fetcher.manual_login_required = True
                log("检测到携程登录弹窗")
        except Exception as login_error:
            if is_browser_session_lost_error(login_error):
                fetcher.browser_session_lost = True
            log(f"登录弹窗检测失败：{type(login_error).__name__}: {login_error}")
        try:
            if fetcher.has_verification_challenge():
                fetcher.captcha_detected = True
                log("检测到携程安全验证弹窗")
        except Exception as challenge_error:
            if is_browser_session_lost_error(challenge_error):
                fetcher.browser_session_lost = True
            log(f"安全验证检测失败：{type(challenge_error).__name__}: {challenge_error}")
        if not page_loaded:
            if fetcher.browser_restart_required:
                log("首页加载失败，下一组将重开浏览器")
            return True
        return False
    except Exception as e:
        if is_browser_session_lost_error(e):
            fetcher.browser_session_lost = True
            reason = f"runner 浏览器会话丢失：{type(e).__name__}, {str(e).split('Stacktrace:')[0].strip()}"
        else:
            reason = f"runner 查询异常：{type(e).__name__}, {str(e).split('Stacktrace:')[0].strip()}"
        log(reason)
        try:
            os.makedirs(".codex", exist_ok=True)
            fetcher.driver.save_screenshot(ERROR_SCREENSHOT_FILE)
            log(f"错误截图已保存：{ERROR_SCREENSHOT_FILE}")
        except Exception as screenshot_error:
            if is_browser_session_lost_error(screenshot_error):
                fetcher.browser_session_lost = True
            log(f"错误截图保存失败：{type(screenshot_error).__name__}: {screenshot_error}")
        try:
            if fetcher.has_login_modal():
                fetcher.manual_login_required = True
                log("检测到携程登录弹窗")
                return False
        except Exception as login_error:
            if is_browser_session_lost_error(login_error):
                fetcher.browser_session_lost = True
            log(f"登录弹窗检测失败：{type(login_error).__name__}: {login_error}")
        try:
            if fetcher.has_verification_challenge():
                fetcher.captcha_detected = True
                log("检测到携程安全验证弹窗")
                return False
        except Exception as challenge_error:
            if is_browser_session_lost_error(challenge_error):
                fetcher.browser_session_lost = True
            log(f"安全验证检测失败：{type(challenge_error).__name__}: {challenge_error}")
        write_failure(fetcher, reason)
        return True


def wait_for_manual_verification(fetcher, wait_seconds):
    deadline = time.time() + wait_seconds
    log(f"请 lyx 在当前 Chrome 窗口手动完成携程安全验证，最多等待 {wait_seconds} 秒")
    while time.time() < deadline:
        try:
            if not fetcher.has_verification_challenge():
                fetcher.save_current_manual_cookies()
                log("携程安全验证已解除")
                return True
        except Exception as e:
            log(f"检查安全验证状态失败：{type(e).__name__}: {e}")
            return False
        time.sleep(5)
    return False


def wait_and_refresh_verification(fetcher, wait_seconds):
    log(f"检测到携程安全验证，先等待 {wait_seconds} 秒后刷新页面重试")
    time.sleep(wait_seconds)
    try:
        fetcher.driver.refresh()
        time.sleep(5)
        if not fetcher.has_verification_challenge():
            fetcher.save_current_manual_cookies()
            log("刷新后携程安全验证已解除")
            return True
        log("刷新后仍检测到携程安全验证")
        return False
    except Exception as e:
        log(f"刷新检查安全验证失败：{type(e).__name__}: {e}")
        return False


def wait_for_manual_login(fetcher, wait_seconds):
    original_wait_seconds = scraper.manual_login_wait_seconds
    scraper.manual_login_wait_seconds = wait_seconds
    try:
        return fetcher.wait_for_manual_login()
    finally:
        scraper.manual_login_wait_seconds = original_wait_seconds


def close_fetcher(fetcher):
    if fetcher is None:
        return
    try:
        fetcher.driver.quit()
    except Exception as e:
        log(f"关闭 driver 失败：{type(e).__name__}: {e}")


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
    parser.add_argument("--all-open-jaw", action="store_true", help="查询全部欧洲城市有序开口程组合，排除进出同城")
    parser.add_argument("--min-interval", type=int, default=5, help="每组查询后的最短等待秒数")
    parser.add_argument("--max-interval", type=int, default=10, help="每组查询后的最长等待秒数")
    parser.add_argument("--max-wait", type=int, default=45, help="首页控件等待秒数")
    parser.add_argument("--max-search-wait", type=int, default=180, help="结果页等待秒数")
    parser.add_argument("--max-consecutive-failures", type=int, default=2, help="连续失败达到该值后停止")
    parser.add_argument("--limit", type=int, default=0, help="本次最多执行的任务数，0 表示不限制")
    parser.add_argument("--run-day", default="", help="结果输出日期目录，默认使用当天日期")
    parser.add_argument("--verification-refresh-wait", type=int, default=90, help="触发安全验证后自动刷新前等待秒数")
    parser.add_argument("--manual-verification-wait", type=int, default=900, help="触发安全验证时等待人工处理的秒数")
    parser.add_argument("--worker-id", default="main", help="worker 标识，用于隔离状态、日志、截图和默认 Chrome profile")
    parser.add_argument("--profile-dir", default="", help="Chrome profile 目录；不传时按 worker-id 使用独立默认目录")
    parser.add_argument("--shard-index", type=int, default=0, help="分片序号，0-based")
    parser.add_argument("--shard-count", type=int, default=1, help="分片总数")
    parser.add_argument("--combine-open-jaw-only", action="store_true", help="只汇总已有开口程航线文件，不启动浏览器查询")
    parser.add_argument("--force", action="store_true", help="忽略已有成功结果，重新执行全部任务")
    return parser.parse_args()


def run_flight_job(args):
    worker_id = configure_worker_files(args.worker_id)
    run_day = args.run_day or dt.now().strftime("%Y-%m-%d")
    scraper.set_result_run_day(run_day)
    scraper.set_chrome_profile_dir(args.profile_dir or default_profile_dir(worker_id))
    cities = scraper.destination_citys if args.all_cities else args.cities
    open_jaw_pairs = args.open_jaw or []
    if args.all_open_jaw:
        open_jaw_pairs = build_all_open_jaw_pairs(scraper.destination_citys) + open_jaw_pairs
    open_jaw_pairs = unique_open_jaw_pairs(open_jaw_pairs)

    scraper.crawl_interval = args.max_interval
    scraper.max_wait_time = args.max_wait
    scraper.max_search_wait_time = args.max_search_wait
    scraper.max_retry_time = 1
    scraper.send_email_after_run = False
    if args.min_interval > args.max_interval:
        raise ValueError("--min-interval 不能大于 --max-interval")

    date_pair_total = count_date_pairs()
    if open_jaw_pairs:
        overall_total_groups = len(open_jaw_pairs) * date_pair_total
        open_jaw_pairs = shard_sequence(open_jaw_pairs, args.shard_index, args.shard_count)
        total_groups = len(open_jaw_pairs) * date_pair_total
        if args.combine_open_jaw_only:
            group_files = write_open_jaw_group_files(open_jaw_pairs)
            combined_file = scraper.write_combined_open_jaw_results(group_files)
            if combined_file:
                log(f"开口程总汇总文件已生成：{combined_file}")
            else:
                log("未找到可汇总的开口程航线文件")
            return
        tasks = build_open_jaw_tasks(open_jaw_pairs, force=args.force)
        run_label = f"all_open_jaw:{len(open_jaw_pairs)} pairs shard {args.shard_index}/{args.shard_count}" if args.all_open_jaw else [f"{pair[0]}<-{pair[1]}" for pair in open_jaw_pairs]
        run_mode = "open_jaw"
    else:
        overall_total_groups = len(cities) * date_pair_total
        cities = shard_sequence(cities, args.shard_index, args.shard_count)
        total_groups = len(cities) * date_pair_total
        tasks = build_roundtrip_tasks(cities, force=args.force)
        run_label = cities
        run_mode = "roundtrip"
    pending_before_limit = len(tasks)
    skipped_existing_results = 0 if args.force else total_groups - pending_before_limit
    if args.limit:
        tasks = tasks[:args.limit]
    status = {
        "started_at": dt.now().isoformat(timespec="seconds"),
        "worker_id": worker_id,
        "shard_index": args.shard_index,
        "shard_count": args.shard_count,
        "mode": run_mode,
        "cities": run_label,
        "overall_total_groups": overall_total_groups,
        "total_groups": total_groups,
        "skipped_existing_results": skipped_existing_results,
        "pending_before_limit": pending_before_limit,
        "total_pending_at_start": len(tasks),
        "completed_this_run": 0,
        "failed_this_run": 0,
        "browser_session_lost_this_run": 0,
        "stopped": False,
        "stop_reason": "",
        "waiting_for_manual_verification": False,
        "waiting_for_manual_login": False,
    }
    write_status(status)
    log(
        f"任务启动：worker {worker_id}，模式 {run_mode}，城市 {run_label}，"
        f"总组合 {overall_total_groups} 组，本分片 {total_groups} 组，"
        f"跳过已有结果 {skipped_existing_results} 组，待执行 {len(tasks)} 组，"
        f"间隔随机 {args.min_interval}-{args.max_interval}s，profile {scraper.CHROME_PROFILE_DIR}"
    )

    if not tasks:
        if run_mode == "roundtrip":
            combined_file = scraper.write_combined_results(scraper.result_files)
            if combined_file:
                log(f"无待执行任务，汇总文件已生成：{combined_file}")
        else:
            group_files = write_open_jaw_group_files(open_jaw_pairs)
            if not group_files:
                log("无待执行开口程任务，未找到可汇总的 raw 文件")
            elif args.shard_count == 1:
                combined_file = scraper.write_combined_open_jaw_results(group_files)
                if combined_file:
                    log(f"无待执行任务，开口程总汇总文件已生成：{combined_file}")
            else:
                log("无待执行任务，分片模式下不在 worker 内生成总汇总")
        return

    fetcher = None
    consecutive_failures = 0

    try:
        for index, task in enumerate(tasks, start=1):
            technical_failure = False
            if fetcher is None:
                fetcher = scraper.DataFetcher(scraper.init_driver())
            fetcher.city = task["route"]
            fetcher.date = task["depart_date"]
            fetcher.return_date = task["return_date"]
            fetcher.query_mode = task.get("mode", "roundtrip")
            fetcher.return_departure_city = task.get("return_departure_city")
            fetcher.err = 0
            fetcher.browser_session_lost = False
            fetcher.browser_restart_required = False
            fetcher.captcha_detected = False
            fetcher.manual_login_required = False

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

            technical_failure = run_query_once(fetcher)

            if fetcher.manual_login_required:
                reason = "检测到登录弹窗，等待 lyx 手动完成登录"
                status["waiting_for_manual_login"] = True
                status["stop_reason"] = reason
                write_status(status)
                log(reason)
                if wait_for_manual_login(fetcher, args.manual_verification_wait):
                    status["waiting_for_manual_login"] = False
                    status["stop_reason"] = ""
                    write_status(status)
                    fetcher.manual_login_required = False
                    log("人工登录完成，重新执行当前组合")
                    technical_failure = run_query_once(fetcher)
                else:
                    reason = "登录等待超时，runner 停止执行"
                    status["waiting_for_manual_login"] = False
                    status["stopped"] = True
                    status["stop_reason"] = reason
                    write_status(status)
                    log(reason)
                    break

            if fetcher.manual_login_required:
                reason = "登录弹窗仍未解除，runner 停止执行"
                status["stopped"] = True
                status["stop_reason"] = reason
                write_status(status)
                log(reason)
                break

            if fetcher.captcha_detected:
                reason = "验证码或风控触发，先等待后刷新页面重试"
                status["stop_reason"] = reason
                write_status(status)
                log(reason)
                if wait_and_refresh_verification(fetcher, args.verification_refresh_wait):
                    status["stop_reason"] = ""
                    write_status(status)
                    fetcher.captcha_detected = False
                    log("自动刷新验证完成，重新执行当前组合")
                    technical_failure = run_query_once(fetcher)
                else:
                    reason = "刷新后验证码或风控仍存在，等待 lyx 手动完成验证"
                    status["waiting_for_manual_verification"] = True
                    status["stop_reason"] = reason
                    write_status(status)
                    log(reason)

                if fetcher.captcha_detected and wait_for_manual_verification(fetcher, args.manual_verification_wait):
                    status["waiting_for_manual_verification"] = False
                    status["stop_reason"] = ""
                    write_status(status)
                    fetcher.captcha_detected = False
                    log("人工验证完成，重新执行当前组合")
                    technical_failure = run_query_once(fetcher)
                elif fetcher.captcha_detected:
                    reason = "验证码或风控等待人工处理超时，runner 停止执行"
                    status["waiting_for_manual_verification"] = False
                    status["stopped"] = True
                    status["stop_reason"] = reason
                    write_status(status)
                    log(reason)
                    break

            if fetcher.captcha_detected:
                reason = "验证码或风控仍未解除，runner 停止执行"
                status["stopped"] = True
                status["stop_reason"] = reason
                write_status(status)
                log(reason)
                break

            if is_success_result(task["output_file"], task["depart_date"], task["return_date"]):
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
            elif is_business_no_result(task["output_file"], task["depart_date"], task["return_date"]):
                consecutive_failures = 0
                status["completed_this_run"] += 1
                scraper.append_result_file(task["output_file"])
                log(f"无航班结果：{task['output_file']}")
            else:
                consecutive_failures += 1
                status["failed_this_run"] += 1
                if not has_result_for_date(task["output_file"], task["depart_date"], task["return_date"]):
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
                if fetcher.browser_session_lost or fetcher.browser_restart_required:
                    if fetcher.browser_session_lost:
                        status["browser_session_lost_this_run"] += 1
                        write_status(status)
                    log("本组技术失败，需要重开浏览器；下一组开始时重新打开")
                    close_fetcher(fetcher)
                    fetcher = None
                else:
                    log("本组技术失败，保留当前浏览器会话；下一组重新导航")

            if index < len(tasks):
                sleep_seconds = random.randint(args.min_interval, args.max_interval)
                log(f"等待 {sleep_seconds} 秒后继续下一组")
                time.sleep(sleep_seconds)
    finally:
        close_fetcher(fetcher)

    if run_mode == "roundtrip":
        combined_file = scraper.write_combined_results(scraper.result_files)
        if combined_file:
            log(f"汇总文件已生成：{combined_file}")
    else:
        group_files = write_open_jaw_group_files(open_jaw_pairs)
        if args.shard_count == 1:
            combined_file = scraper.write_combined_open_jaw_results(group_files)
            if combined_file:
                log(f"开口程总汇总文件已生成：{combined_file}")
        else:
            log("分片模式下不在 worker 内生成总汇总；全部 worker 完成后运行 --combine-open-jaw-only")
    log("任务结束")


def main():
    args = parse_args()
    run_flight_job(args)


if __name__ == "__main__":
    main()
