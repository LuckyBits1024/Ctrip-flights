import argparse
import os
from datetime import datetime as dt

import ctrip_browser_context_api as browser_api
import flight_query_config as flight_config


LOG_FILE = os.path.join(".codex", "browser_api_job.log")


def now_text():
    return dt.now().strftime("%Y-%m-%d_%H-%M-%S")


def log(message):
    line = f"{now_text()} {message}"
    print(line, flush=True)
    os.makedirs(".codex", exist_ok=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")


def parse_args():
    parser = argparse.ArgumentParser(description="通过真实浏览器页面捕获携程国际 batchSearch API 查询开口程价格")
    parser.add_argument("--cities", nargs="+", default=flight_config.destination_citys, help="目的地城市列表")
    parser.add_argument("--run-day", default=dt.now().strftime("%Y-%m-%d"), help="结果输出日期目录")
    parser.add_argument("--timeout", type=int, default=45, help="单个页面等待 batchSearch 成功响应的秒数")
    parser.add_argument("--request-interval", type=float, default=5.0, help="每个单程日期查询之间的等待秒数")
    parser.add_argument("--max-requests", type=int, default=0, help="本次最多执行的单程日期查询数，0 表示不限制")
    parser.add_argument("--profile-dir", default=None, help="Chrome 用户数据目录，默认复用 .codex/chrome-profile")
    parser.add_argument("--max-consecutive-auth", type=int, default=5, help="连续安全验证达到该次数后冷却重开 Chrome")
    parser.add_argument("--auth-cooldown", type=int, default=180, help="连续安全验证后的冷却秒数")
    return parser.parse_args()


def main():
    args = parse_args()
    output_file = browser_api.run_browser_api_job(
        cities=args.cities,
        run_day=args.run_day,
        timeout=args.timeout,
        request_interval=args.request_interval,
        max_requests=args.max_requests,
        profile_dir=args.profile_dir,
        max_consecutive_auth=args.max_consecutive_auth,
        auth_cooldown=args.auth_cooldown,
        log=log,
    )
    log(f"任务结束：{output_file}")


if __name__ == "__main__":
    main()
