from datetime import datetime as dt, timedelta


origin_city = "上海"

# 德国、法国、意大利、瑞士主要机场城市
destination_citys = [
    "巴黎",
    "法兰克福",
    "慕尼黑",
    "柏林",
    "杜塞尔多夫",
    "汉堡",
    "尼斯",
    "里昂",
    "马赛",
    "罗马",
    "米兰",
    "威尼斯",
    "佛罗伦萨",
    "那不勒斯",
    "苏黎世",
    "日内瓦",
    "巴塞尔",
]

# 爬取日期范围：起始日期。格式'2023-12-01'
begin_date = "2026-09-25"

# 爬取日期范围：结束日期。格式'2023-12-31'
end_date = "2026-10-10"

# 往返最短间隔天数
min_stay_days = 7

# 爬取T+N，即N天后
start_interval = 1

# 爬取的日期
crawl_days = 16

# 日期间隔
days_interval = 1


def generate_flight_dates(n, begin_date, end_date, start_interval, days_interval):
    flight_dates = []
    if begin_date:
        begin_date = dt.strptime(begin_date, "%Y-%m-%d")
    else:
        begin_date = dt.now() + timedelta(days=start_interval)

    for i in range(0, n, days_interval):
        flight_date = begin_date + timedelta(days=i)
        flight_dates.append(flight_date.strftime("%Y-%m-%d"))

    if end_date:
        end_date = dt.strptime(end_date, "%Y-%m-%d")
        flight_dates = [date for date in flight_dates if dt.strptime(date, "%Y-%m-%d") <= end_date]

        while dt.strptime(flight_dates[-1], "%Y-%m-%d") < end_date:
            next_date = dt.strptime(flight_dates[-1], "%Y-%m-%d") + timedelta(days=days_interval)
            if next_date <= end_date:
                flight_dates.append(next_date.strftime("%Y-%m-%d"))
            else:
                break

    return flight_dates


def generate_round_trip_dates(begin_date, end_date, min_stay_days, days_interval):
    depart_dates = generate_flight_dates(crawl_days, begin_date, end_date, start_interval, days_interval)
    return_dates = generate_flight_dates(crawl_days, begin_date, end_date, start_interval, days_interval)
    round_trip_dates = []
    for depart_date in depart_dates:
        depart_dt = dt.strptime(depart_date, "%Y-%m-%d")
        for return_date in return_dates:
            return_dt = dt.strptime(return_date, "%Y-%m-%d")
            if (return_dt - depart_dt).days >= min_stay_days:
                round_trip_dates.append((depart_date, return_date))
    return round_trip_dates
