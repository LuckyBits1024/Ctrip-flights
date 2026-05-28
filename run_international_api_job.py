import argparse
import os
from datetime import datetime as dt

import ctrip_international_api as international_api
import flight_query_config as flight_config


LOG_FILE = os.path.join(".codex", "international_api_job.log")


def now_text():
    return dt.now().strftime("%Y-%m-%d_%H-%M-%S")


def log(message):
    line = f"{now_text()} {message}"
    print(line, flush=True)
    os.makedirs(".codex", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="通过携程国际机票 batchSearch API 查询开口程价格")
    parser.add_argument("--cities", nargs="+", default=flight_config.destination_citys, help="目的地城市列表")
    parser.add_argument("--run-day", default=dt.now().strftime("%Y-%m-%d"), help="结果输出日期目录")
    parser.add_argument("--no-cookies", action="store_true", help="不读取 cookies.json 中的手动登录 Cookie")
    parser.add_argument("--timeout", type=int, default=30, help="单个 API 请求超时秒数")
    parser.add_argument("--request-interval", type=float, default=2.0, help="每个单程日期 API 查询之间的等待秒数")
    parser.add_argument("--max-requests", type=int, default=0, help="本次最多执行的单程日期 API 查询数，0 表示不限制")
    parser.add_argument("--debug-print", action="store_true", help="打印国际搜索页表单、sign、batchSearch 请求和完整响应")
    return parser.parse_args()


def main():
    args = parse_args()
    output_file = international_api.run_international_api_job(
        cities=args.cities,
        run_day=args.run_day,
        use_cookies=not args.no_cookies,
        timeout=args.timeout,
        request_interval=args.request_interval,
        max_requests=args.max_requests,
        debug_print=args.debug_print,
        log=log,
    )
    log(f"任务结束：{output_file}")


if __name__ == "__main__":
    main()
