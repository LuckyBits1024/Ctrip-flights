import argparse
import os
from datetime import datetime as dt

import flight_query_config as flight_config
import ctrip_lowest_price_api as lowest_price_api


LOG_FILE = os.path.join(".codex", "lowest_price_api_job.log")


def now_text():
    return dt.now().strftime("%Y-%m-%d_%H-%M-%S")


def log(message):
    line = f"{now_text()} {message}"
    print(line, flush=True)
    os.makedirs(".codex", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="通过携程 lowestPrice API 查询开口程低价日历")
    parser.add_argument("--cities", nargs="+", default=flight_config.destination_citys, help="目的地城市列表")
    parser.add_argument("--run-day", default=dt.now().strftime("%Y-%m-%d"), help="结果输出日期目录")
    parser.add_argument("--include-same-city", action="store_true", help="包含上海-巴黎、巴黎-上海这类进出同城组合")
    parser.add_argument("--direct", action="store_true", help="只查直飞低价")
    parser.add_argument("--timeout", type=int, default=20, help="单个 API 请求超时秒数")
    parser.add_argument("--request-interval", type=float, default=2.0, help="每条 API 航线之间的等待秒数")
    return parser.parse_args()


def main():
    args = parse_args()
    output_file = lowest_price_api.run_api_lowest_price_job(
        cities=args.cities,
        run_day=args.run_day,
        include_same_city=args.include_same_city,
        direct=args.direct,
        timeout=args.timeout,
        request_interval=args.request_interval,
        log=log,
    )
    log(f"任务结束：{output_file}")


if __name__ == "__main__":
    main()
