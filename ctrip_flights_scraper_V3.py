import os
import glob
import gzip
import time
import json
import re
import mimetypes
import smtplib
import pandas as pd
from seleniumwire import webdriver
from datetime import datetime as dt, timedelta
from email.message import EmailMessage
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException
import threading

origin_city = "上海"

# 爬取的欧洲主要城市
destination_citys = [
    "巴黎",
    "法兰克福",
    "阿姆斯特丹",
    "马德里",
    "罗马",
    "米兰",
    "慕尼黑",
    "苏黎世",
    "维也纳",
    "伊斯坦布尔",
    "赫尔辛基",
    "哥本哈根",
    "巴塞罗那",
    "布鲁塞尔",
    "都柏林",
    "布拉格",
    "雅典",
    "里斯本",
    "斯德哥尔摩",
    "奥斯陆",
    "华沙",
]

# 爬取的航线
crawl_routes = [[origin_city, city] for city in destination_citys]

# 爬取日期范围：起始日期。格式'2023-12-01'
begin_date = '2026-09-25'

# 爬取日期范围：结束日期。格式'2023-12-31'
end_date = '2026-10-10'

# 往返最短间隔天数
min_stay_days = 9

# 爬取T+N，即N天后
start_interval = 1

# 爬取的日期
crawl_days = 16

# 设置各城市爬取的时间间隔（单位：秒）
crawl_interval = 30

# 日期间隔
days_interval = 1

# 设置页面加载的最长等待时间（单位：秒）
max_wait_time = 60

# 等待航班结果接口完成的最长时间（单位：秒）
max_search_wait_time = 120

# 最大错误重试次数
max_retry_time = 3

# 页面失败后的重试等待时间（单位：秒）
retry_wait_time = 30

# 是否只抓取直飞信息（True: 只抓取直飞，False: 抓取所有航班）
direct_flight = False

# 是否抓取航班舒适信息（True: 抓取，False: 不抓取）
comft_flight = False

# 是否删除不重要的信息
del_info = False

# 是否重命名DataFrame的列名
rename_col = True

# 调试截图
enable_screenshot = False

# 允许登录（可能必须要登录才能获取数据）
login_allowed = True

# 账号
accounts = ['','']

# 密码
passwords = ['','']

#本地登录缓存
COOKIES_FILE = "cookies.json"
MANUAL_COOKIE_ACCOUNT = "manual_login"
REQUIRED_COOKIES = ["AHeadUserInfo", "DUID", "IsNonUser", "_udl", "cticket", "login_type", "login_uid"]
manual_login_wait_seconds = 600

# 邮件发送配置
SENDER_EMAILS = "1264932425@qq.com"
RECEIVER_EMAIL = "1264932425@qq.com"
EMAIL_PASSWORD = "kabyhxldvwbojfgj"
SMTP_SERVER = "smtp.qq.com"
SMTP_PORT = 465

# 程序结束后是否自动发邮件；本任务要求先给 lyx 预览，默认关闭。
send_email_after_run = False

result_files = []
result_run_day = dt.now().strftime("%Y-%m-%d")

OPEN_JAW_COLUMNS = [
    "状态",
    "查询日期",
    "查询模式",
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
    "排序方式",
    "价格说明",
    "往返含税价",
    "开口程含税价",
    "去程展示信息",
    "去程按钮文案",
    "回程展示信息",
    "回程按钮文案",
]

def append_result_file(filename):
    if filename not in result_files:
        result_files.append(filename)

def set_result_run_day(run_day):
    global result_run_day
    result_run_day = run_day

def wait_before_retry(stage):
    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} {stage}：等待 {retry_wait_time} 秒后重试')
    time.sleep(retry_wait_time)

def send_result_email(files):
    if not files:
        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 没有生成机票结果文件，跳过邮件发送')
        return

    msg = EmailMessage()
    msg["Subject"] = f"携程机票往返价格结果：{origin_city}-欧洲 {begin_date} 至 {end_date}"
    msg["From"] = SENDER_EMAILS
    msg["To"] = RECEIVER_EMAIL

    body = [
        "本轮携程机票往返价格查询完成。",
        f"出发地：{origin_city}",
        f"目的地数量：{len(destination_citys)}",
        f"去程出发日期范围：{begin_date} 至 {end_date}",
        f"回程出发日期范围：{begin_date} 至 {end_date}",
        f"最短停留天数：{min_stay_days}",
        "",
        "结果文件：",
    ]
    body.extend([f"{os.path.basename(os.path.dirname(os.path.dirname(path)))}_{os.path.basename(path)}" for path in files])
    msg.set_content("\n".join(body))

    for path in files:
        ctype, encoding = mimetypes.guess_type(path)
        if ctype is None or encoding is not None:
            ctype = "text/csv"
        maintype, subtype = ctype.split("/", 1)
        attachment_name = f"{os.path.basename(os.path.dirname(os.path.dirname(path)))}_{os.path.basename(path)}"
        with open(path, "rb") as f:
            msg.add_attachment(
                f.read(),
                maintype=maintype,
                subtype=subtype,
                filename=attachment_name,
            )

    with smtplib.SMTP_SSL(SMTP_SERVER, SMTP_PORT) as server:
        server.login(SENDER_EMAILS, EMAIL_PASSWORD)
        server.send_message(msg)

    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 机票结果邮件发送成功：{RECEIVER_EMAIL}')

def init_driver():
    options = webdriver.ChromeOptions()
    options.page_load_strategy = "eager"
    options.add_argument("--incognito")  # 隐身模式（无痕模式）
    # options.add_argument('--headless')  # 启用无头模式
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-blink-features")
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_argument("--disable-extensions")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--ignore-certificate-errors")
    options.add_argument("--ignore-certificate-errors-spki-list")
    options.add_argument("--ignore-ssl-errors")
    options.add_experimental_option("excludeSwitches", ["enable-automation"])  # 不显示正在受自动化软件控制的提示
    driver = webdriver.Chrome(options=options)
    driver.maximize_window()

    return driver

def gen_citys(crawl_citys):
    # 生成城市组合表
    citys = []
    ytic = list(reversed(crawl_citys))
    for m in crawl_citys:
        for n in ytic:
            if m == n:
                continue
            else:
                citys.append([m, n])
    return citys

def generate_flight_dates(n, begin_date, end_date, start_interval, days_interval):
    flight_dates = []
    
    if begin_date:
        begin_date = dt.strptime(begin_date, "%Y-%m-%d")
    elif start_interval:
        begin_date = dt.now() + timedelta(days=start_interval)
        
    for i in range(0, n, days_interval):
        flight_date = begin_date + timedelta(days=i)

        flight_dates.append(flight_date.strftime("%Y-%m-%d"))
    
    # 如果有结束日期，确保生成的日期不超过结束日期
    if end_date:
        end_date = dt.strptime(end_date, "%Y-%m-%d")
        flight_dates = [date for date in flight_dates if dt.strptime(date, "%Y-%m-%d") <= end_date]
        # 继续生成日期直到达到或超过结束日期
        while dt.strptime(flight_dates[-1], "%Y-%m-%d") < end_date:
            next_date = dt.strptime(flight_dates[-1], "%Y-%m-%d") + timedelta(days=days_interval)
            if next_date <= end_date:
                flight_dates.append(next_date.strftime("%Y-%m-%d"))
            else:
                break
    
    return flight_dates

def generate_round_trip_dates(begin_date, end_date, min_stay_days, days_interval):
    depart_dates = generate_flight_dates(crawl_days, begin_date, end_date, start_interval, days_interval)
    date_pairs = []
    for depart_date in depart_dates:
        depart_dt = dt.strptime(depart_date, "%Y-%m-%d")
        for return_date in depart_dates:
            return_dt = dt.strptime(return_date, "%Y-%m-%d")
            if (return_dt - depart_dt).days >= min_stay_days:
                date_pairs.append((depart_date, return_date))
    return date_pairs

def result_file_path(city, depart_date=None, return_date=None):
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{begin_date}_to_{end_date}",
        result_run_day,
    )
    filename = f"{city[0]}-{city[1]}.csv"
    return os.path.join(files_dir, filename)

def sort_by_price(frame):
    for column in ["往返含税价", "开口程含税价", "经济舱总价"]:
        if column in frame.columns:
            frame["_sort_price"] = pd.to_numeric(frame[column], errors="coerce")
            frame = frame.sort_values("_sort_price", ascending=True, na_position="last")
            return frame.drop(columns=["_sort_price"])
    return frame

def open_jaw_group_key(outbound_destination, return_departure_city):
    return f"{origin_city}-{outbound_destination}__{return_departure_city}-{origin_city}"

def open_jaw_raw_result_file_path(outbound_destination, return_departure_city, depart_date, return_date):
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{begin_date}_to_{end_date}",
        result_run_day,
        "open_jaw",
        "raw",
    )
    filename = f"{open_jaw_group_key(outbound_destination, return_departure_city)}_{depart_date}_return_{return_date}.csv"
    return os.path.join(files_dir, filename)

def open_jaw_group_result_file_path(outbound_destination, return_departure_city):
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{begin_date}_to_{end_date}",
        result_run_day,
        "open_jaw",
    )
    filename = f"{open_jaw_group_key(outbound_destination, return_departure_city)}.csv"
    return os.path.join(files_dir, filename)

def write_open_jaw_group_results(outbound_destination, return_departure_city):
    pattern = os.path.join(
        os.getcwd(),
        "results",
        f"{begin_date}_to_{end_date}",
        result_run_day,
        "open_jaw",
        "raw",
        f"{open_jaw_group_key(outbound_destination, return_departure_city)}_*.csv",
    )
    files = sorted(glob.glob(pattern))
    frames = []
    for path in files:
        if os.path.exists(path):
            frame = pd.read_csv(path)
            for column in OPEN_JAW_COLUMNS:
                if column not in frame.columns:
                    frame[column] = ""
            frames.append(frame[OPEN_JAW_COLUMNS])

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined = sort_by_price(combined)

    group_file = open_jaw_group_result_file_path(outbound_destination, return_departure_city)
    files_dir = os.path.dirname(group_file)
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)
    combined.to_csv(group_file, encoding="UTF-8", index=False)
    return group_file

def write_combined_results(files):
    if not files:
        return None

    frames = []
    for path in files:
        if os.path.exists(path):
            frames.append(pd.read_csv(path))

    if not frames:
        return None

    combined = pd.concat(frames, ignore_index=True)
    combined = sort_by_price(combined)
    files_dir = os.path.join(
        os.getcwd(),
        "results",
        f"{begin_date}_to_{end_date}",
        result_run_day,
    )
    if not os.path.exists(files_dir):
        os.makedirs(files_dir)
    combined_file = os.path.join(files_dir, f"{origin_city}-欧洲往返机票汇总.csv")
    combined.to_csv(combined_file, encoding="UTF-8", index=False)
    return combined_file

# element_to_be_clickable 函数来替代 expected_conditions.element_to_be_clickable 或 expected_conditions.visibility_of_element_located
def element_to_be_clickable(element):
    def check_clickable(driver):
        try:
            if element.is_enabled() and element.is_displayed():
                return element  # 当条件满足时，返回元素本身
            else:
                return False
        except:
            return False

    return check_clickable

class DataFetcher(object):
    def __init__(self, driver):
        self.driver = driver
        self.date = None
        self.return_date = None
        self.city = None
        self.query_mode = "roundtrip"
        self.return_departure_city = None
        self.err = 0  # 错误重试次数
        self.switch_acc = 0 #切换账户
        self.comfort_data = None  # 航班舒适度信息
        self.manual_cookies_loaded = False
        self.captcha_detected = False

    def refresh_driver(self):
        try:
            self.driver.refresh()
        except Exception as e:
            # 错误次数+1
            self.err += 1

            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} refresh_driver:刷新页面失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )
            
            # 保存错误截图
            if enable_screenshot:
                self.driver.save_screenshot(
                    f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                )
            if self.err < max_retry_time:
                # 刷新页面
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} refresh_driver：刷新页面')
                self.refresh_driver()

            # 判断错误次数
            if self.err >= max_retry_time:
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,refresh_driver:不继续重试'
                )
    
    def remove_btn(self):
        try:
            #WebDriverWait(self.driver, max_wait_time).until(lambda d: d.execute_script('return typeof jQuery !== "undefined"'))
            # 移除提醒
            self.driver.execute_script("document.querySelectorAll('.notice-box').forEach(element => element.remove());")
            # 移除在线客服
            self.driver.execute_script("document.querySelectorAll('.shortcut, .shortcut-link').forEach(element => element.remove());")
            # 移除分享链接
            self.driver.execute_script("document.querySelectorAll('.shareline').forEach(element => element.remove());")
            # 移除透明风控动画 iframe，避免遮挡点击
            self.driver.execute_script("document.querySelectorAll('#stageFrame').forEach(element => element.remove());")
            '''
            # 使用JavaScript删除有的<dl>标签
            self.driver.execute_script("""
                var elements = document.getElementsByTagName('dl');
                while(elements.length > 0){
                    elements[0].parentNode.removeChild(elements[0]);
                }
            """)
            '''
        except Exception as e:
            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} remove_btn:提醒移除失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )

    def check_verification_code(self):
        try:
            # 检查是否有验证码元素，如果有，则需要人工处理
            if self.has_verification_challenge():
                self.captcha_detected = True
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} check_verification_code：验证码或风控被触发，停止当前自动化执行。')
                return False
            else:
                # 移除注意事项
                self.remove_btn()
                # 如果没有找到验证码元素，则说明页面加载成功，没有触发验证码
                return True
        except Exception as e:
            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} check_verification_code:未知错误，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )
            return False

    def has_verification_challenge(self):
        challenge_texts = [
            "为保障您的安全访问",
            "依次点击图标验证",
            "请完成以下操作",
        ]
        if len(self.driver.find_elements(By.ID, "verification-code")):
            return True
        if len(self.driver.find_elements(By.CLASS_NAME, "alert-title")):
            return True
        page_text = self.driver.page_source
        return any(text in page_text for text in challenge_texts)

    def load_cookies(self, account):
        if os.path.exists(COOKIES_FILE):
            try:
                with open(COOKIES_FILE, "r") as f:
                    cookies_all = json.load(f)
                return cookies_all.get(account)
            except Exception as e:
                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} load_cookies: 读取 cookies 出错：{e}")
                return None
        return None

    def save_cookies(self, account, cookies):
        cookies_all = {}
        if os.path.exists(COOKIES_FILE):
            try:
                with open(COOKIES_FILE, "r") as f:
                    cookies_all = json.load(f)
            except Exception:
                cookies_all = {}
        cookies_all[account] = cookies
        with open(COOKIES_FILE, "w") as f:
            json.dump(cookies_all, f)

    def has_login_modal(self):
        return len(self.driver.find_elements(By.CLASS_NAME, "lg_loginbox_modal")) > 0

    def save_current_manual_cookies(self):
        cookies = [
            cookie
            for cookie in self.driver.get_cookies()
            if "ctrip.com" in cookie.get("domain", "") or "trip.com" in cookie.get("domain", "")
        ]
        self.save_cookies(MANUAL_COOKIE_ACCOUNT, cookies)
        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 已保存 {len(cookies)} 条携程 cookies")

    def load_manual_cookies(self):
        if self.manual_cookies_loaded:
            return

        cookies = self.load_cookies(MANUAL_COOKIE_ACCOUNT)
        if not cookies:
            return

        for cookie in cookies:
            self.driver.add_cookie(cookie)
        self.manual_cookies_loaded = True
        self.driver.refresh()
        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 已加载本地携程 cookies")

    def wait_for_manual_login(self):
        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 请在弹出的 Chrome 中完成携程登录", flush=True)
        deadline = time.time() + manual_login_wait_seconds
        while time.time() < deadline:
            cookie_names = {cookie.get("name") for cookie in self.driver.get_cookies()}
            if any(cookie_name in cookie_names for cookie_name in REQUIRED_COOKIES) and not self.has_login_modal():
                self.save_current_manual_cookies()
                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 检测到登录完成", flush=True)
                return True
            time.sleep(5)

        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 等待登录超时", flush=True)
        return False

    def delete_cookies(self, account):
        try:
            if os.path.exists(COOKIES_FILE):
                with open(COOKIES_FILE, "r") as f:
                    cookies_all = json.load(f)
                if account in cookies_all:
                    del cookies_all[account]
                    with open(COOKIES_FILE, "w") as f:
                        json.dump(cookies_all, f)
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 成功删除账号 {account} 的 cookies")
        except Exception as e:
            print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 删除账号 {account} cookies 失败：{e}")

    def login(self):
        if login_allowed:
            
            account = accounts[self.switch_acc % len(accounts)]
            password = passwords[self.switch_acc % len(passwords)]
            
            # ===== 尝试使用本地缓存的 cookies 登录 =====
            local_cookies = self.load_cookies(account)
            if local_cookies:
                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 检测到本地 cookies，尝试通过 cookies 登录")
                for cookie in local_cookies:
                    try:
                        self.driver.add_cookie(cookie)
                    except Exception as e:
                        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 添加 cookie {cookie.get('name')} 失败：{e}")
                
                try:
                    # 检测登录状态，通过https://my.ctrip.com/myinfo/home
                    self.driver.get('https://my.ctrip.com/myinfo/home')
                    
                    WebDriverWait(self.driver, max_wait_time).until(
                        lambda d: d.current_url == 'https://my.ctrip.com/myinfo/home'
                    )
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: 已通过 cookie 登录")
                    self.err += 99
                    return 1
                except Exception:
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 错误次数【{self.err}-{max_retry_time}】 login: cookie 登录失效，重新走登录流程")
                    self.err += 1
                    if self.err >= max_retry_time:
                        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} login: cookie 登录失败次数超过 {max_retry_time} 次，删除该账号 cookies")
                        self.delete_cookies(account)
                        self.err = 0
                    self.login()
            else:
                try:
                    if len(self.driver.find_elements(By.CLASS_NAME, "lg_loginbox_modal")) == 0:
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:未弹出登录界面')
                        WebDriverWait(self.driver, max_wait_time).until(EC.presence_of_element_located((By.CLASS_NAME, "tl_nfes_home_header_login_wrapper_siwkn")))
                        # 点击飞机图标，返回主界面
                        ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_element(By.CLASS_NAME, "tl_nfes_home_header_login_wrapper_siwkn")))
                        ele.click()
                        #等待页面加载
                        WebDriverWait(self.driver, max_wait_time).until(EC.presence_of_element_located((By.CLASS_NAME, "lg_loginwrap")))
                    else:
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:已经弹出登录界面')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_elements(By.CSS_SELECTOR, ".r_input.bbz-js-iconable-input")[0]))
                    ele.send_keys(account)
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:输入账户成功')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_element(By.CSS_SELECTOR, "div[data-testid='accountPanel'] input[data-testid='passwordInput']")))
                    ele.send_keys(password)
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:输入密码成功')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_element(By.CSS_SELECTOR, '[for="checkboxAgreementInput"]')))
                    ele.click()
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login:勾选同意成功')
                    
                    ele = WebDriverWait(self.driver, max_wait_time).until(element_to_be_clickable(self.driver.find_elements(By.CSS_SELECTOR, ".form_btn.form_btn--block")[0]))
                    ele.click()
    
                    # 检查是否出现验证码验证页面（max_wait_time秒内检测）
                    try:
                        WebDriverWait(self.driver, max_wait_time).until(
                            EC.presence_of_element_located((By.CSS_SELECTOR, "[data-testid='doubleAuthSwitcherBox']"))
                        )
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 检测到验证码验证页面')
                        
                        # 定义验证码弹窗的父级选择器
                        double_auth_selector = "[data-testid='doubleAuthSwitcherBox']"
                        
                        # 从 doubleAuthSwitcherBox 内定位发送验证码按钮并点击
                        send_btn = WebDriverWait(self.driver, max_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, f"{double_auth_selector} dl[data-testid='dynamicCodeInput'] a.btn-primary-s"))
                        )
                        send_btn.click()
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 发送验证码按钮点击')
                        
                        # 使用线程等待用户在控制台输入验证码，超时则按超时处理逻辑
                        verification_code = [None]
                        user_input_completed = threading.Event()
                        
                        def wait_for_verification_input():
                            verification_code[0] = input("请输入收到的验证码: ")
                            user_input_completed.set()
                        
                        input_thread = threading.Thread(target=wait_for_verification_input)
                        input_thread.start()
                        timeout_seconds = crawl_interval * 100
                        input_thread.join(timeout=timeout_seconds)
                        
                        if not user_input_completed.is_set():
                            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 验证码输入超时 {timeout_seconds} 秒')
                            self.switch_acc += 1
                            self.err += 99
                            return 0
                        
                        # 从 doubleAuthSwitcherBox 内定位验证码输入框，并输入验证码
                        code_input = WebDriverWait(self.driver, max_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, f"{double_auth_selector} input[data-testid='verifyCodeInput']"))
                        )
                        code_input.send_keys(verification_code[0])
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 验证码输入成功')
                        
                        # 从 doubleAuthSwitcherBox 内定位并点击“验 证”按钮
                        verify_btn = WebDriverWait(self.driver, max_wait_time).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, f"{double_auth_selector} dl[data-testid='dynamicVerifyButton'] input[type='submit']"))
                        )
                        verify_btn.click()
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 验证码提交成功')
                        
                        # 等待验证码验证后的页面加载，比如首页的某个关键元素
                        WebDriverWait(self.driver, max_wait_time).until(
                            EC.presence_of_element_located((By.CLASS_NAME, "pc_home-jipiao"))
                        )
                    except Exception as e:
                        # 如果max_wait_time秒内未检测到验证码页面，则认为是正常登录流程
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: 未检测到验证码验证页面，继续执行')
                    
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login：登录成功')
                    # 保存登录截图
                    if enable_screenshot:
                        self.driver.save_screenshot(
                            f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                        )
                    time.sleep(crawl_interval*3)
                    
                    # ===== 登录成功后提取需要的 cookies 并保存 =====
                    all_cookies = self.driver.get_cookies()
                    filtered_cookies = [ck for ck in all_cookies if ck.get("name") in REQUIRED_COOKIES]
                    self.save_cookies(account, filtered_cookies)
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login: cookies 已保存')
                    
                except Exception as e:
                    # 错误次数+1
                    self.err += 1
                    # 用f字符串格式化错误类型和错误信息，提供更多的调试信息
                    print(
                        f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login：页面加载或元素操作失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
                    )
        
                    # 保存错误截图
                    if enable_screenshot:
                        self.driver.save_screenshot(
                            f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                        )
                        
                    if self.err < max_retry_time:
                        # 刷新页面
                        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} login：刷新页面')
                        self.refresh_driver()
                        # 检查注意事项和验证码
                        if self.check_verification_code():
                            # 重试
                            self.login()
                    # 判断错误次数
                    if self.err >= max_retry_time:
                        print(
                            f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,login:重新尝试加载页面，这次指定需要重定向到首页'
                        )

    def get_page(self, reset_to_homepage=0):
        next_stage_flag = False
        try:
            if reset_to_homepage == 1:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 尝试前往首页...')
                start_time = time.time()
                # 前往首页
                self.driver.get(
                    "https://flights.ctrip.com/online/channel/domestic")
                self.load_manual_cookies()
                end_time = time.time()
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 前往首页耗时: {end_time - start_time:.2f} 秒')

            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 当前页面 URL: {self.driver.current_url}')
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 当前页面标题: {self.driver.title}')

            # 检查注意事项和验证码
            if self.check_verification_code():
                if self.query_mode == "open_jaw":
                    self.select_trip_type("多程")
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 等待页面加载完成...')
                WebDriverWait(self.driver, max_wait_time).until(
                    EC.presence_of_element_located(
                        (By.CLASS_NAME, "form-input-v3"))
                )
                if self.query_mode == "open_jaw":
                    WebDriverWait(self.driver, max_wait_time).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, ".form-input-v2")) >= 6
                    )
                    WebDriverWait(self.driver, max_wait_time).until(
                        lambda d: len(d.find_elements(By.CSS_SELECTOR, ".modifyDate")) >= 3
                    )
                else:
                    WebDriverWait(self.driver, max_wait_time).until(
                        EC.presence_of_element_located(
                            (By.CSS_SELECTOR, ".modifyDate.return-date"))
                    )
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 页面加载完成')
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已确认当前页面为{self.query_mode}查询')

                next_stage_flag = True
        except Exception as e:
            self.err += 1
            # 用f字符串格式化错误类型和错误信息，提供更多的调试信息
            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_page：页面加载或元素操作失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )
            try:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 当前页面 URL: {self.driver.current_url}')
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 当前页面标题: {self.driver.title}')
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 当前页面源代码: {self.driver.page_source[:500]}...')  # 只打印前500个字符
            except Exception as page_error:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_page：读取当前页面状态失败，错误类型：{type(page_error).__name__}, 详细错误信息：{str(page_error).split("Stacktrace:")[0]}')

            # 保存错误截图
            if enable_screenshot:
                screenshot_path = f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                self.driver.save_screenshot(screenshot_path)
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误截图已保存: {screenshot_path}')

            if self.err < max_retry_time:
                wait_before_retry("get_page")
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 重新尝试加载页面，这次指定需要重定向到首页')
                self.get_page(1)
            else:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,get_page:不继续刷新')
                self.err = 0
        else:
            if next_stage_flag:
                # 继续下一步
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 页面加载成功，继续下一步')
                if self.query_mode == "open_jaw":
                    self.change_open_jaw_city()
                else:
                    self.change_city()
            else:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 页面加载成功，但未能完成所有操作')

    def select_trip_type(self, label):
        tabs = WebDriverWait(self.driver, max_wait_time).until(
            lambda d: [
                item
                for item in d.find_elements(By.CSS_SELECTOR, ".form-select-radio-group li")
                if label in item.text and item.is_displayed() and item.is_enabled()
            ]
        )
        for tab in tabs:
            if tab.is_displayed() and tab.is_enabled():
                tab.click()
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已选择查询类型：{label}')
                return
        raise RuntimeError(f"未找到查询类型：{label}")

    def fill_city_input(self, input_index, city_name):
        for _ in range(3):
            WebDriverWait(self.driver, max_wait_time).until(
                lambda d: len(d.find_elements(By.CLASS_NAME, "form-input-v3")) > input_index
            )
            city_input = self.driver.find_elements(By.CLASS_NAME, "form-input-v3")[input_index]
            if city_name in city_input.get_attribute("value"):
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：更换城市【{input_index}】-'
                    f'{city_input.get_attribute("value")}'
                )
                return

            ele = WebDriverWait(self.driver, max_wait_time).until(
                element_to_be_clickable(city_input)
            )
            ele.click()
            ele.send_keys(Keys.COMMAND + "a")
            ele = WebDriverWait(self.driver, max_wait_time).until(
                element_to_be_clickable(self.driver.find_elements(By.CLASS_NAME, "form-input-v3")[input_index])
            )
            ele.send_keys(city_name)
            time.sleep(1)
            ele.send_keys(Keys.ENTER)
            time.sleep(1)

        value = self.driver.find_elements(By.CLASS_NAME, "form-input-v3")[input_index].get_attribute("value")
        raise RuntimeError(f"未能填写城市输入框【{input_index}】：目标 {city_name}，当前 {value}")

    def fill_city_input_by_selector(self, selector, city_name):
        for _ in range(3):
            city_input = WebDriverWait(self.driver, max_wait_time).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, selector))
            )
            if city_name in city_input.get_attribute("value"):
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：更换城市【{selector}】-'
                    f'{city_input.get_attribute("value")}'
                )
                return

            ele = WebDriverWait(self.driver, max_wait_time).until(
                element_to_be_clickable(city_input)
            )
            ele.click()
            ele.send_keys(Keys.COMMAND + "a")
            ele.send_keys(city_name)
            time.sleep(1)
            ele.send_keys(Keys.ENTER)
            time.sleep(1)

        value = self.driver.find_element(By.CSS_SELECTOR, selector).get_attribute("value")
        raise RuntimeError(f"未能填写城市输入框【{selector}】：目标 {city_name}，当前 {value}")

    def change_city(self):
        next_stage_flag = False
        try:
            # 等待页面完成加载
            WebDriverWait(self.driver, max_wait_time).until(
                EC.presence_of_element_located(
                    (By.CLASS_NAME, "form-input-v3"))
            )

            # 检查注意事项和验证码
            if self.check_verification_code():
                if self.has_login_modal():
                    if self.wait_for_manual_login():
                        self.err = 0
                    else:
                        return

                del self.driver.requests

                # 若出发地与目标值不符，则更改出发地
                while self.city[0] not in self.driver.find_elements(
                    By.CLASS_NAME, "form-input-v3"
                )[0].get_attribute("value"):
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(
                                By.CLASS_NAME, "form-input-v3")[0]
                        )
                    )
                    ele.click()
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(
                                By.CLASS_NAME, "form-input-v3")[0]
                        )
                    )
                    ele.send_keys(Keys.COMMAND + "a")
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(
                                By.CLASS_NAME, "form-input-v3")[0]
                        )
                    )
                    ele.send_keys(self.city[0])
                    time.sleep(1)
                    ele.send_keys(Keys.ENTER)

                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：更换城市【0】-{self.driver.find_elements(By.CLASS_NAME,"form-input-v3")[0].get_attribute("value")}'
                )

                # 若目的地与目标值不符，则更改目的地
                while self.city[1] not in self.driver.find_elements(
                    By.CLASS_NAME, "form-input-v3"
                )[1].get_attribute("value"):
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(
                                By.CLASS_NAME, "form-input-v3")[1]
                        )
                    )
                    ele.click()
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(
                                By.CLASS_NAME, "form-input-v3")[1]
                        )
                    )
                    ele.send_keys(Keys.COMMAND + "a")
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(
                                By.CLASS_NAME, "form-input-v3")[1]
                        )
                    )
                    ele.send_keys(self.city[1])
                    time.sleep(1)
                    ele.send_keys(Keys.ENTER)

                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：更换城市【1】-{self.driver.find_elements(By.CLASS_NAME,"form-input-v3")[1].get_attribute("value")}'
                )

                self.select_date(self.date, ".modifyDate.depart-date")
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：更换日期-{self.get_date_value(".modifyDate.depart-date")}'
                )

                self.select_date(self.return_date, ".modifyDate.return-date")
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：更换返程日期-{self.get_date_value(".modifyDate.return-date")}'
                )
                self.close_date_picker()

                self.confirm_city_selected(0)
                self.confirm_city_selected(1)

                del self.driver.requests

                ele = WebDriverWait(self.driver, max_wait_time).until(
                    element_to_be_clickable(
                        self.driver.find_element(By.CLASS_NAME, "search-btn")
                    )
                )
                ele.click()
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：点击搜索按钮')

                next_stage_flag = True

        except Exception as e:
            # 错误次数+1
            self.err += 1

            # 保存错误截图
            if enable_screenshot:
                self.driver.save_screenshot(
                    f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                )

            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,change_city：更换城市和日期失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )

            if self.has_login_modal():
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：检测到登录弹窗，等待手动登录'
                )
                if self.wait_for_manual_login():
                    self.err = 0
                    self.change_city()
                return

            # 检查注意事项和验证码
            if self.check_verification_code():
                if self.err < max_retry_time:
                    # 重试
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：重试')
                    self.change_city()
                # 判断错误次数
                if self.err >= max_retry_time:
                    print(
                        f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,change_city:不继续重试'
                    )

                    # 重置错误计数
                    self.err = 0
                    self.records = [self.build_no_result_record("页面交互失败")]
                    self.write_roundtrip_data()
        else:
            if next_stage_flag:
                # 若无错误，执行下一步
                self.collect_low_price_roundtrip_from_page()

                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_city：成功更换城市和日期，当前路线为：{self.city[0]}-{self.city[1]}，去程：{self.date}，返程：{self.return_date}')

    def change_open_jaw_city(self):
        next_stage_flag = False
        try:
            WebDriverWait(self.driver, max_wait_time).until(
                lambda d: len(d.find_elements(By.CSS_SELECTOR, ".form-input-v2")) >= 6
            )

            if self.check_verification_code():
                if self.has_login_modal():
                    if self.wait_for_manual_login():
                        self.err = 0
                    else:
                        return

                return_departure_city = self.return_departure_city
                if not return_departure_city:
                    raise RuntimeError("open_jaw 模式缺少返程出发城市")

                del self.driver.requests

                self.fill_city_input_by_selector("input[name='mtDCity1']", self.city[0])
                self.fill_city_input_by_selector("input[name='mtACity1']", self.city[1])
                self.fill_city_input_by_selector("input[name='mtDCity2']", return_departure_city)
                self.fill_city_input_by_selector("input[name='mtACity2']", self.city[0])

                self.select_date_by_index(self.date, 0)
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_open_jaw_city：更换第一程日期-{self.get_date_value_by_index(0)}'
                )

                self.select_date_by_index(self.return_date, 1)
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_open_jaw_city：更换第二程日期-{self.get_date_value_by_index(1)}'
                )

                for selector in [
                    "input[name='mtDCity1']",
                    "input[name='mtACity1']",
                    "input[name='mtDCity2']",
                    "input[name='mtACity2']",
                ]:
                    self.confirm_city_selected_by_selector(selector)

                del self.driver.requests

                ele = WebDriverWait(self.driver, max_wait_time).until(
                    element_to_be_clickable(self.driver.find_element(By.CLASS_NAME, "search-btn"))
                )
                ele.click()
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_open_jaw_city：点击搜索按钮')

                next_stage_flag = True

        except Exception as e:
            self.err += 1
            if enable_screenshot:
                self.driver.save_screenshot(
                    f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                )

            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,change_open_jaw_city：更换城市和日期失败，错误类型：{type(e).__name__}, 详细错误信息：{str(e).split("Stacktrace:")[0]}'
            )

            if self.has_login_modal():
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_open_jaw_city：检测到登录弹窗，等待手动登录'
                )
                if self.wait_for_manual_login():
                    self.err = 0
                    self.change_open_jaw_city()
                return

            if self.check_verification_code():
                if self.err < max_retry_time:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_open_jaw_city：重试')
                    self.change_open_jaw_city()
                if self.err >= max_retry_time:
                    print(
                        f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,change_open_jaw_city:不继续重试'
                    )
                    self.err = 0
                    self.records = [self.build_no_result_record("开口程页面交互失败")]
                    self.write_roundtrip_data()
        else:
            if next_stage_flag:
                self.collect_low_price_open_jaw_from_page()

                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} change_open_jaw_city：成功更换城市和日期，当前开口程为：{self.city[0]}-{self.city[1]} / {self.return_departure_city}-{self.city[0]}，去程：{self.date}，返程：{self.return_date}'
                )

    def get_date_value(self, trigger_selector):
        return self.driver.find_element(
            By.CSS_SELECTOR,
            f"{trigger_selector} input[aria-label=请选择日期]",
        ).get_attribute("value")

    def get_date_value_by_index(self, trigger_index):
        return self.driver.find_elements(
            By.CSS_SELECTOR,
            ".modifyDate input[aria-label=请选择日期]",
        )[trigger_index].get_attribute("value")

    def close_date_picker(self):
        self.driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
        time.sleep(0.5)

    def select_date(self, target_date, trigger_selector):
        target = dt.strptime(target_date, "%Y-%m-%d")
        for _ in range(3):
            try:
                while self.get_date_value(trigger_selector) != target_date:
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        EC.element_to_be_clickable((By.CSS_SELECTOR, trigger_selector))
                    )
                    ele.click()

                    for _ in range(24):
                        pickers = self.driver.find_elements(By.CSS_SELECTOR, ".date-picker.date-picker-block")
                        left_year = int(pickers[0].find_element(By.CLASS_NAME, "year").text[:-1])
                        left_month = int(pickers[0].find_element(By.CLASS_NAME, "month").text[:-1])
                        right_year = int(pickers[1].find_element(By.CLASS_NAME, "year").text[:-1])
                        right_month = int(pickers[1].find_element(By.CLASS_NAME, "month").text[:-1])
                        left_key = left_year * 12 + left_month
                        right_key = right_year * 12 + right_month
                        target_key = target.year * 12 + target.month

                        if target_key < left_key:
                            ele = WebDriverWait(self.driver, max_wait_time).until(
                                element_to_be_clickable(
                                    self.driver.find_elements(
                                        By.CSS_SELECTOR,
                                        ".in-date-picker.icon.prev-ico.iconf-left",
                                    )[0]
                                )
                            )
                            ele.click()
                            continue

                        if target_key > right_key:
                            ele = WebDriverWait(self.driver, max_wait_time).until(
                                element_to_be_clickable(
                                    self.driver.find_elements(
                                        By.CSS_SELECTOR,
                                        ".in-date-picker.icon.next-ico.iconf-right",
                                    )[1]
                                )
                            )
                            ele.click()
                            continue

                        for picker in self.driver.find_elements(By.CSS_SELECTOR, ".date-picker.date-picker-block"):
                            year = int(picker.find_element(By.CLASS_NAME, "year").text[:-1])
                            month = int(picker.find_element(By.CLASS_NAME, "month").text[:-1])
                            if year != target.year or month != target.month:
                                continue

                            for day in picker.find_elements(By.CLASS_NAME, "date-d"):
                                if day.text and int(day.text) == target.day:
                                    day.click()
                                    WebDriverWait(self.driver, max_wait_time).until(
                                        lambda d: self.get_date_value(trigger_selector) == target_date
                                    )
                                    return

                    raise RuntimeError(f"未能选择日期：{target_date}")
                return
            except StaleElementReferenceException:
                time.sleep(1)

        raise RuntimeError(f"日期控件刷新导致选择失败：{target_date}")

    def select_date_by_index(self, target_date, trigger_index):
        target = dt.strptime(target_date, "%Y-%m-%d")
        for _ in range(3):
            try:
                while self.get_date_value_by_index(trigger_index) != target_date:
                    ele = WebDriverWait(self.driver, max_wait_time).until(
                        element_to_be_clickable(
                            self.driver.find_elements(By.CSS_SELECTOR, ".modifyDate")[trigger_index]
                        )
                    )
                    ele.click()

                    for _ in range(24):
                        pickers = self.driver.find_elements(By.CSS_SELECTOR, ".date-picker.date-picker-block")
                        left_year = int(pickers[0].find_element(By.CLASS_NAME, "year").text[:-1])
                        left_month = int(pickers[0].find_element(By.CLASS_NAME, "month").text[:-1])
                        right_year = int(pickers[1].find_element(By.CLASS_NAME, "year").text[:-1])
                        right_month = int(pickers[1].find_element(By.CLASS_NAME, "month").text[:-1])
                        left_key = left_year * 12 + left_month
                        right_key = right_year * 12 + right_month
                        target_key = target.year * 12 + target.month

                        if target_key < left_key:
                            arrows = [
                                arrow for arrow in self.driver.find_elements(
                                    By.CSS_SELECTOR,
                                    ".in-date-picker.icon.prev-ico.iconf-left",
                                )
                                if arrow.is_displayed() and arrow.is_enabled()
                            ]
                            if not arrows:
                                raise RuntimeError("未找到可点击的日期上一页按钮")
                            ele = WebDriverWait(self.driver, max_wait_time).until(
                                element_to_be_clickable(arrows[0])
                            )
                            ele.click()
                            time.sleep(0.5)
                        elif target_key > right_key:
                            arrows = [
                                arrow for arrow in self.driver.find_elements(
                                    By.CSS_SELECTOR,
                                    ".in-date-picker.icon.next-ico.iconf-right",
                                )
                                if arrow.is_displayed() and arrow.is_enabled()
                            ]
                            if not arrows:
                                raise RuntimeError("未找到可点击的日期下一页按钮")
                            ele = WebDriverWait(self.driver, max_wait_time).until(
                                element_to_be_clickable(arrows[-1])
                            )
                            ele.click()
                            time.sleep(0.5)
                        else:
                            break

                    clicked = False
                    for picker in self.driver.find_elements(By.CSS_SELECTOR, ".date-picker.date-picker-block"):
                        year = int(picker.find_element(By.CLASS_NAME, "year").text[:-1])
                        month = int(picker.find_element(By.CLASS_NAME, "month").text[:-1])
                        if year != target.year or month != target.month:
                            continue

                        for date_ele in picker.find_elements(By.CSS_SELECTOR, ".date-day"):
                            days = date_ele.find_elements(By.CLASS_NAME, "date-d")
                            if days and days[0].text and int(days[0].text) == target.day:
                                ele = WebDriverWait(self.driver, max_wait_time).until(
                                    element_to_be_clickable(date_ele)
                                )
                                ele.click()
                                clicked = True
                                WebDriverWait(self.driver, max_wait_time).until(
                                    lambda d: self.get_date_value_by_index(trigger_index) == target_date
                                )
                                break
                        if clicked:
                            break

                    if not clicked:
                        raise RuntimeError(f"未能选择日期：{target_date}")
                return
            except StaleElementReferenceException:
                time.sleep(1)

        raise RuntimeError(f"日期控件刷新导致选择失败：{target_date}")

    def confirm_city_selected(self, input_index):
        for _ in range(3):
            city_input = self.driver.find_elements(By.CLASS_NAME, "form-input-v3")[input_index]
            if "(" in city_input.get_attribute("value"):
                return

            ele = WebDriverWait(self.driver, max_wait_time).until(
                element_to_be_clickable(city_input)
            )
            ele.click()
            ele.send_keys(Keys.ENTER)
            time.sleep(1)

        value = self.driver.find_elements(By.CLASS_NAME, "form-input-v3")[input_index].get_attribute("value")
        raise RuntimeError(f"未能确认城市输入框【{input_index}】：{value}")

    def confirm_city_selected_by_selector(self, selector):
        for _ in range(3):
            city_input = self.driver.find_element(By.CSS_SELECTOR, selector)
            if "(" in city_input.get_attribute("value"):
                return

            ele = WebDriverWait(self.driver, max_wait_time).until(
                element_to_be_clickable(city_input)
            )
            ele.click()
            ele.send_keys(Keys.ENTER)
            time.sleep(1)

        value = self.driver.find_element(By.CSS_SELECTOR, selector).get_attribute("value")
        raise RuntimeError(f"未能确认城市输入框【{selector}】：{value}")

    def select_low_price_sort(self, stage):
        ele = WebDriverWait(self.driver, max_search_wait_time).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, "li.sort-item.ticket-price"))
        )
        if "active" not in ele.get_attribute("class"):
            ele.click()
            WebDriverWait(self.driver, max_search_wait_time).until(
                lambda d: "active" in d.find_element(By.CSS_SELECTOR, "li.sort-item.ticket-price").get_attribute("class")
            )
            time.sleep(2)
        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} {stage}：已选择低价优先')

    def first_flight_item(self):
        return WebDriverWait(self.driver, max_search_wait_time).until(
            EC.element_to_be_clickable((By.CSS_SELECTOR, ".flight-item"))
        )

    def first_bookable_flight_item(self):
        return WebDriverWait(self.driver, max_search_wait_time).until(
            lambda d: next(
                (
                    item
                    for item in d.find_elements(By.CSS_SELECTOR, ".flight-item")
                    if item.is_displayed() and "订票" in item.text
                ),
                False,
            )
        )

    def wait_for_return_stage(self):
        def is_return_stage(driver):
            active_tabs = driver.find_elements(By.CSS_SELECTOR, ".segment_tab.active")
            if any("选择返程" in tab.text for tab in active_tabs):
                return True
            body_text = driver.find_element(By.TAG_NAME, "body").text
            return "选择返程" in body_text and self.city[1] in body_text and self.city[0] in body_text

        WebDriverWait(self.driver, max_search_wait_time).until(is_return_stage)

    def extract_visible_flight(self, item):
        text = item.text.replace("\n", " ")
        price_match = re.search(r"¥\s*([\d,]+)", text)
        price = int(price_match.group(1).replace(",", "")) if price_match else ""
        action = ""
        buttons = item.find_elements(By.CSS_SELECTOR, ".btn.btn-book")
        if buttons:
            action = buttons[0].text
        return {
            "展示信息": text,
            "往返含税价": price,
            "按钮文案": action,
        }

    def collect_low_price_roundtrip_from_page(self):
        stay_days = (dt.strptime(self.return_date, "%Y-%m-%d") - dt.strptime(self.date, "%Y-%m-%d")).days

        self.select_low_price_sort("去程")
        outbound_item = self.first_flight_item()
        outbound_info = self.extract_visible_flight(outbound_item)
        outbound_button = outbound_item.find_element(By.CSS_SELECTOR, ".btn.btn-book")
        outbound_button.click()

        self.wait_for_return_stage()
        self.select_low_price_sort("返程")
        return_item = self.first_flight_item()
        return_info = self.extract_visible_flight(return_item)

        price = return_info["往返含税价"] or outbound_info["往返含税价"]
        self.records = [
            {
                "状态": "成功",
                "查询日期": dt.now().strftime("%Y-%m-%d"),
                "出发城市": self.city[0],
                "目的城市": self.city[1],
                "去程出发日期": self.date,
                "回程出发日期": self.return_date,
                "停留天数": stay_days,
                "排序方式": "去程低价优先；返程低价优先",
                "价格说明": "页面低价优先首条往返含税价",
                "往返含税价": price,
                "去程展示信息": outbound_info["展示信息"],
                "去程按钮文案": outbound_info["按钮文案"],
                "回程展示信息": return_info["展示信息"],
                "回程按钮文案": return_info["按钮文案"],
            }
        ]
        self.write_roundtrip_data()

    def active_segment_text(self):
        segments = self.driver.find_elements(By.CSS_SELECTOR, ".segment_tab.active")
        if segments:
            return segments[0].text
        return ""

    def collect_low_price_open_jaw_from_page(self):
        stay_days = (dt.strptime(self.return_date, "%Y-%m-%d") - dt.strptime(self.date, "%Y-%m-%d")).days
        return_departure_city = self.return_departure_city
        if not return_departure_city:
            raise RuntimeError("open_jaw 模式缺少返程出发城市")

        self.select_low_price_sort("第一程")
        outbound_item = self.first_flight_item()
        outbound_info = self.extract_visible_flight(outbound_item)
        outbound_button = outbound_item.find_element(By.CSS_SELECTOR, ".btn.btn-book")
        outbound_button.click()

        WebDriverWait(self.driver, max_search_wait_time).until(
            lambda d: "第二程" in d.find_element(By.TAG_NAME, "body").text
            and return_departure_city in d.find_element(By.TAG_NAME, "body").text
            and self.city[0] in d.find_element(By.TAG_NAME, "body").text
        )
        self.select_low_price_sort("第二程")
        return_item = self.first_bookable_flight_item()
        return_info = self.extract_visible_flight(return_item)

        price = return_info["往返含税价"]
        if not price:
            self.records = [self.build_no_result_record("未读到开口程产品含税价")]
            self.write_roundtrip_data()
            return

        self.records = [
            {
                "状态": "成功",
                "查询日期": dt.now().strftime("%Y-%m-%d"),
                "查询模式": "开口程",
                "开口程组合": open_jaw_group_key(self.city[1], return_departure_city),
                "出发城市": self.city[0],
                "目的城市": self.city[1],
                "去程出发城市": self.city[0],
                "去程到达城市": self.city[1],
                "返程出发城市": return_departure_city,
                "返程到达城市": self.city[0],
                "去程出发日期": self.date,
                "回程出发日期": self.return_date,
                "停留天数": stay_days,
                "排序方式": "第一程低价优先；第二程低价优先",
                "价格说明": "携程多程页面第二程低价优先首条展示含税价",
                "往返含税价": price,
                "开口程含税价": price,
                "去程展示信息": outbound_info["展示信息"],
                "去程按钮文案": outbound_info["按钮文案"],
                "回程展示信息": return_info["展示信息"],
                "回程按钮文案": return_info["按钮文案"],
            }
        ]
        self.write_roundtrip_data()

    def decode_search_response(self, request):
        body = request.response.body
        content_encoding = request.response.headers.get("Content-Encoding", "").lower()
        if "gzip" in content_encoding:
            body = gzip.decompress(body)
        return json.loads(body.decode("UTF-8"))

    def is_matching_search_request(self, request):
        if "/international/search/api/search/batchSearch" not in request.url:
            return False

        request_data = json.loads(request.body)
        request_segments = request_data.get("flightSegments", [])
        if len(request_segments) < 2:
            return False

        outbound = dict(request_segments[0])
        inbound = dict(request_segments[1])
        if self.query_mode == "open_jaw":
            if not self.return_departure_city:
                return False
            return (
                self.city[0] in outbound.get("departureCityName", "")
                and self.city[1] in outbound.get("arrivalCityName", "")
                and outbound.get("departureDate") == self.date
                and self.return_departure_city in inbound.get("departureCityName", "")
                and self.city[0] in inbound.get("arrivalCityName", "")
                and inbound.get("departureDate") == self.return_date
            )

        return (
            outbound.get("departureCityName") == self.city[0]
            and self.city[1] in outbound.get("arrivalCityName", "")
            and outbound.get("departureDate") == self.date
            and self.city[1] in inbound.get("departureCityName", "")
            and inbound.get("arrivalCityName") == self.city[0]
            and inbound.get("departureDate") == self.return_date
        )

    def wait_for_search_result(self):
        deadline = time.time() + max_search_wait_time
        matched_requests = 0

        while time.time() < deadline:
            for request in reversed(self.driver.requests):
                if not request.response:
                    continue

                try:
                    if not self.is_matching_search_request(request):
                        continue

                    matched_requests += 1
                    response_data = self.decode_search_response(request)
                    data = response_data.get("data", {})
                    if "flightItineraryList" in data or "searchErrorInfo" in data:
                        return request, response_data

                    context = data.get("context", {})
                    if context.get("finished") is True:
                        return request, response_data
                except Exception:
                    continue

            time.sleep(1)

        raise TimeoutError(f"等待航班结果超时，匹配请求数：{matched_requests}")

    def get_data(self):
        try:
            if comft_flight:
                # 捕获 getFlightComfort 数据
                self.comfort_data = self.capture_flight_comfort_data()

            self.predata, self.dedata = self.wait_for_search_result()

        except Exception as e:
            # 错误次数+1
            self.err += 1

            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,get_data:获取数据超时，错误类型：{type(e).__name__}, 错误详细：{str(e).split("Stacktrace:")[0]}'
            )

            # 保存错误截图
            if enable_screenshot:
                self.driver.save_screenshot(
                    f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                )

            # 删除本次请求
            del self.driver.requests

            if self.err < max_retry_time:
                # 刷新页面
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} get_data：刷新页面')
                self.refresh_driver()

                # 检查注意事项和验证码
                if self.check_verification_code():
                    # 重试
                    self.get_data()

            # 判断错误次数
            if self.err >= max_retry_time:
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,get_data:不继续重试'
                )

                # 重置错误计数
                self.err = 0
                self.records = [self.build_no_result_record("获取数据超时")]
                self.write_roundtrip_data()
        else:
            # 删除本次请求
            del self.driver.requests

            print(f"get_data:往返结果获取成功：{self.city[0]}-{self.city[1]} {self.date} / {self.return_date}")
            self.err = 0
            self.check_data()

    def decode_data(self):
        try:
            body = self.predata.response.body
            content_encoding = self.predata.response.headers.get("Content-Encoding", "").lower()
            if "gzip" in content_encoding:
                body = gzip.decompress(body)
            
            self.dedata = json.loads(body.decode("UTF-8"))

        except Exception as e:
            # 错误次数+1
            self.err += 1

            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,decode_data:数据解码失败，错误类型：{type(e).__name__}, 错误详细：{str(e).split("Stacktrace:")[0]}'
            )

            # 保存错误截图
            if enable_screenshot:
                self.driver.save_screenshot(
                    f'screenshot/screenshot_{time.strftime("%Y-%m-%d_%H-%M-%S")}.png'
                )

            # 删除本次请求
            del self.driver.requests

            if self.err < max_retry_time:
                # 刷新页面
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} decode_data：刷新页面')
                self.refresh_driver()

                # 检查注意事项和验证码
                if self.check_verification_code():
                    # 重试
                    self.get_data()
            # 判错错误次数
            if self.err >= max_retry_time:
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,decode_data:不继续重试'
                )

                # 重置错误计数
                self.err = 0
                self.records = [self.build_no_result_record("数据解码失败")]
                self.write_roundtrip_data()
        else:
            # 重置错误计数
            self.err = 0

            # 若无错误，执行下一步
            self.check_data()

    def check_data(self):
        try:
            self.flightItineraryList = self.dedata["data"]["flightItineraryList"]
            if len(self.flightItineraryList) == 0:
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 不存在航班:{self.city[0]}-{self.city[1]} {self.date}/{self.return_date}')
                self.records = [self.build_no_result_record("无航班结果")]
                self.write_roundtrip_data()
                self.err = 0
                return 0
        except Exception as e:
            # 错误次数+1
            self.err += 1
            print(
                f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 数据检查出错：不存在航班，错误类型：{type(e).__name__}, 错误详细：{str(e).split("Stacktrace:")[0]}'
            )
            print(self.dedata)
            if self.err < max_retry_time:
                if 'searchErrorInfo' in self.dedata["data"]:
                    # 重置错误计数
                    self.err = 0
                    return 0
                else:
                    if "'needUserLogin': True" in str(self.dedata["data"]):
                        print(
                            f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,check_data:必须要登录才能查看数据，这次指定需要重定向到首页'
                        )
                        # 重新尝试加载页面，这次指定需要重定向到首页
                        self.login()
                    
                    # 刷新页面
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} check_data：刷新页面')
                    self.refresh_driver()
                    # 检查注意事项和验证码
                    if self.check_verification_code():
                        # 重试
                        self.get_data()
            # 判断错误次数
            if self.err >= max_retry_time:
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 错误次数【{self.err}-{max_retry_time}】,check_data:不继续重试'
                )

                # 重置错误计数
                self.err = 0
                self.records = [self.build_no_result_record("数据检查失败")]
                self.write_roundtrip_data()
        else:
            # 重置错误计数
            self.err = 0
            self.proc_roundtrip_itineraries()
            self.write_roundtrip_data()

    def build_no_result_record(self, reason):
        record = {
            "状态": reason,
            "查询日期": dt.now().strftime("%Y-%m-%d"),
            "出发城市": self.city[0],
            "目的城市": self.city[1],
            "去程出发日期": self.date,
            "回程出发日期": self.return_date,
            "停留天数": (dt.strptime(self.return_date, "%Y-%m-%d") - dt.strptime(self.date, "%Y-%m-%d")).days,
        }
        if self.query_mode == "open_jaw":
            record.update(
                {
                    "查询模式": "开口程",
                    "开口程组合": open_jaw_group_key(self.city[1], self.return_departure_city),
                    "出发城市": self.city[0],
                    "目的城市": self.city[1],
                    "去程出发城市": self.city[0],
                    "去程到达城市": self.city[1],
                    "返程出发城市": self.return_departure_city,
                    "返程到达城市": self.city[0],
                    "排序方式": "",
                    "价格说明": "",
                    "往返含税价": "",
                    "开口程含税价": "",
                    "去程展示信息": "",
                    "去程按钮文案": "",
                    "回程展示信息": "",
                    "回程按钮文案": "",
                }
            )
        return record

    def extract_price_info(self, price_list):
        price_info = {}
        cabin_map = {"Y": "经济舱", "C": "商务舱"}

        for cabin_code, cabin_name in cabin_map.items():
            candidates = []
            for price in price_list:
                if price.get("cabin") != cabin_code:
                    continue

                adult_price = price.get("adultPrice", 0)
                if price.get("freeOilFeeAndTax"):
                    adult_tax = price.get("adultTax", 0)
                else:
                    adult_tax = price.get("adultTax", price.get("sortPrice", adult_price) - adult_price)

                candidates.append(
                    {
                        "票价": adult_price,
                        "税费": adult_tax,
                        "总价": adult_price + adult_tax,
                        "指标": price.get("miseryIndex", ""),
                    }
                )

            if candidates:
                best = min(candidates, key=lambda item: item["总价"])
                price_info[f"{cabin_name}票价"] = best["票价"]
                price_info[f"{cabin_name}税费"] = best["税费"]
                price_info[f"{cabin_name}总价"] = best["总价"]
                price_info[f"{cabin_name}指标"] = best["指标"]
            else:
                price_info[f"{cabin_name}票价"] = ""
                price_info[f"{cabin_name}税费"] = ""
                price_info[f"{cabin_name}总价"] = ""
                price_info[f"{cabin_name}指标"] = ""

        return price_info

    def format_flight_unit(self, flight):
        flight_no = flight.get("flightNo", "")
        airline = flight.get("marketAirlineName", "")
        departure = f'{flight.get("departureCityName", "")}{flight.get("departureAirportName", "")}({flight.get("departureAirportCode", "")})'
        arrival = f'{flight.get("arrivalCityName", "")}{flight.get("arrivalAirportName", "")}({flight.get("arrivalAirportCode", "")})'
        text = (
            f'{airline}{flight_no} '
            f'{departure} {flight.get("departureDateTime", "")} -> '
            f'{arrival} {flight.get("arrivalDateTime", "")}'
        )

        stop_list = flight.get("stopList") or []
        if stop_list:
            stop_text = "、".join(
                [
                    f'{stop.get("cityName", "")}({stop.get("airportName", "")}, {stop.get("duration", "")}分钟)'
                    for stop in stop_list
                ]
            )
            text = f"{text} 经停[{stop_text}]"

        return text

    def format_segment(self, segment):
        flights = segment.get("flightList", [])
        chain = " | ".join([self.format_flight_unit(flight) for flight in flights])
        transfer_chain = " | ".join(
            [
                f'{flight.get("arrivalCityName", "")}{flight.get("arrivalAirportName", "")}({flight.get("arrivalAirportCode", "")})'
                for flight in flights[:-1]
            ]
        )
        first = flights[0] if flights else {}
        last = flights[-1] if flights else {}

        return {
            "航班链": chain,
            "中转次数": segment.get("transferCount", ""),
            "中转机场链": transfer_chain,
            "出发机场": first.get("departureAirportName", ""),
            "出发机场三字码": first.get("departureAirportCode", ""),
            "到达机场": last.get("arrivalAirportName", ""),
            "到达机场三字码": last.get("arrivalAirportCode", ""),
            "出发时间": first.get("departureDateTime", ""),
            "到达时间": last.get("arrivalDateTime", ""),
            "总飞行时长": segment.get("duration", ""),
        }

    def proc_roundtrip_itineraries(self):
        self.records = []
        stay_days = (dt.strptime(self.return_date, "%Y-%m-%d") - dt.strptime(self.date, "%Y-%m-%d")).days

        for index, itinerary in enumerate(self.flightItineraryList, start=1):
            segments = itinerary["flightSegments"]
            price_info = self.extract_price_info(itinerary.get("priceList", []))
            outbound_info = self.format_segment(segments[0])
            if len(segments) > 1:
                inbound_info = self.format_segment(segments[1])
                inbound_detail_status = "已展开"
            else:
                inbound_info = {
                    "航班链": "首轮往返报价未展开回程明细",
                    "中转次数": "",
                    "中转机场链": "",
                    "出发机场": "",
                    "出发机场三字码": "",
                    "到达机场": "",
                    "到达机场三字码": "",
                    "出发时间": "",
                    "到达时间": "",
                    "总飞行时长": "",
                }
                inbound_detail_status = "未展开"

            record = {
                "状态": "成功",
                "查询日期": dt.now().strftime("%Y-%m-%d"),
                "出发城市": self.city[0],
                "目的城市": self.city[1],
                "去程出发日期": self.date,
                "回程出发日期": self.return_date,
                "停留天数": stay_days,
                "方案序号": index,
                "携程行程ID": itinerary.get("itineraryId", ""),
                "价格说明": "携程首轮响应中的往返总价",
                "回程明细状态": inbound_detail_status,
            }
            record.update(price_info)
            record.update({f"去程{key}": value for key, value in outbound_info.items()})
            record.update({f"回程{key}": value for key, value in inbound_info.items()})
            self.records.append(record)

    def write_roundtrip_data(self):
        try:
            if self.query_mode == "open_jaw":
                normalized_records = []
                for record in self.records:
                    normalized_records.append({column: record.get(column, "") for column in OPEN_JAW_COLUMNS})
                self.df = pd.DataFrame(normalized_records, columns=OPEN_JAW_COLUMNS)
                filename = open_jaw_raw_result_file_path(
                    self.city[1],
                    self.return_departure_city,
                    self.date,
                    self.return_date,
                )
            else:
                new_frame = pd.DataFrame(self.records)
                filename = result_file_path(self.city, self.date, self.return_date)
                if os.path.exists(filename):
                    existing_frame = pd.read_csv(filename)
                    same_date = (
                        (existing_frame["去程出发日期"].astype(str) == self.date)
                        & (existing_frame["回程出发日期"].astype(str) == self.return_date)
                    )
                    existing_frame = existing_frame[~same_date]
                    self.df = pd.concat([existing_frame, new_frame], ignore_index=True)
                else:
                    self.df = new_frame
                self.df = sort_by_price(self.df)
            files_dir = os.path.dirname(filename)
            if not os.path.exists(files_dir):
                os.makedirs(files_dir)

            self.df.to_csv(filename, encoding="UTF-8", index=False)
            append_result_file(filename)
            if self.query_mode == "open_jaw":
                group_file = write_open_jaw_group_results(self.city[1], self.return_departure_city)
                if group_file:
                    print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 开口程汇总文件已更新 {group_file}')

            print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 数据查询完成 {filename} 行数：{len(self.df)}\n')
            return filename

        except Exception as e:
            print(f"写入往返数据失败 {str(e)}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            import traceback
            print(f"错误堆栈: {traceback.format_exc()}")
            raise

    def proc_flightSegments(self):
        self.flights = pd.DataFrame()

        for flightlist in self.flightItineraryList:
            flightlist = flightlist["flightSegments"][0]["flightList"]
            flightUnitList = dict(flightlist[0])

            departureday = flightUnitList["departureDateTime"].split(" ")[0]
            departuretime = flightUnitList["departureDateTime"].split(" ")[1]

            arrivalday = flightUnitList["arrivalDateTime"].split(" ")[0]
            arrivaltime = flightUnitList["arrivalDateTime"].split(" ")[1]

            # 处理 stopList
            if 'stopList' in flightUnitList and flightUnitList['stopList']:
                stop_info = []
                for stop in flightUnitList['stopList']:
                    stop_info.append(f"{stop['cityName']}({stop['airportName']}, {stop['duration']}分钟)")
                flightUnitList['stopInfo'] = ' -> '.join(stop_info)
            else:
                flightUnitList['stopInfo'] = '无中转'

            if del_info:
                # 删除一些不重要的信息
                dellist = [
                    "sequenceNo",
                    "marketAirlineCode",
                    "departureProvinceId",
                    "departureCityId",
                    "departureCityCode",
                    "departureAirportShortName",
                    "departureTerminal",
                    "arrivalProvinceId",
                    "arrivalCityId",
                    "arrivalCityCode",
                    "arrivalAirportShortName",
                    "arrivalTerminal",
                    "transferDuration",
                    "stopList",
                    "leakedVisaTagSwitch",
                    "trafficType",
                    "highLightPlaneNo",
                    "mealType",
                    "operateAirlineCode",
                    "arrivalDateTime",
                    "departureDateTime",
                    "operateFlightNo",
                    "operateAirlineName",
                ]
                for value in dellist:
                    flightUnitList.pop(value, None)

            # 更新日期格式
            flightUnitList.update(
                {
                    "departureday": departureday,
                    "departuretime": departuretime,
                    "arrivalday": arrivalday,
                    "arrivaltime": arrivaltime,
                }
            )

            self.flights = pd.concat(
                [
                    self.flights,
                    pd.DataFrame.from_dict(flightUnitList, orient="index").T,
                ],
                ignore_index=True,
            )

    def proc_priceList(self):
        self.prices = pd.DataFrame()

        for flightlist in self.flightItineraryList:
            flightNo = flightlist["itineraryId"].split("_")[0]
            priceList = flightlist["priceList"]

            # 经济舱，经济舱折扣
            economy, economy_tax, economy_total, economy_full = [], [], [], []
            economy_origin_price, economy_tax_price, economy_total_price, economy_full_price = "", "", "", ""
            # 商务舱，商务舱折扣
            bussiness, bussiness_tax, bussiness_total, bussiness_full = [], [], [], []
            bussiness_origin_price, bussiness_tax_price, bussiness_total_price, bussiness_full_price = "", "", "", ""

            for price in priceList:
                # print("Price dictionary keys:", price.keys())
                # print("Full price dictionary:", json.dumps(price, indent=2))
                
                adultPrice = price["adultPrice"]
                childPrice = price.get("childPrice", adultPrice)  # 如果没有childPrice，使用adultPrice
                freeOilFeeAndTax = price["freeOilFeeAndTax"]
                sortPrice = price.get("sortPrice", adultPrice)  # 如果没有sortPrice，使用adultPrice
                
                # 估算税费（如果需要的话）
                estimatedTax = sortPrice - adultPrice if not freeOilFeeAndTax else 0
                adultTax = price.get("adultTax", estimatedTax)  # 如果没有adultTax，使用estimatedTax

                miseryIndex = price["miseryIndex"]
                cabin = price["cabin"]

                # 经济舱
                if cabin == "Y":
                    economy.append(adultPrice)
                    economy_tax.append(adultTax)
                    economy_full.append(miseryIndex)
                    economy_total.append(adultPrice+adultTax)
                # 商务舱
                elif cabin == "C":
                    bussiness.append(adultPrice)
                    bussiness_tax.append(adultTax)
                    bussiness_full.append(miseryIndex)
                    bussiness_total.append(adultPrice+adultTax)

            # 初始化变量
            economy_min_index = None
            bussiness_min_index = None
            
            if economy_total != []:
                economy_total_price = min(economy_total)
                economy_min_index = economy_total.index(economy_total_price)
            
            if bussiness_total != []:
                bussiness_total_price = min(bussiness_total)
                bussiness_min_index = bussiness_total.index(bussiness_total_price)
            
            if economy_min_index is not None:
                economy_origin_price = economy[economy_min_index]
                economy_tax_price = economy_tax[economy_min_index]
                economy_full_price = economy_full[economy_min_index]
            
            if bussiness_min_index is not None:
                bussiness_origin_price = bussiness[bussiness_min_index]
                bussiness_tax_price = bussiness_tax[bussiness_min_index]
                bussiness_full_price = bussiness_full[bussiness_min_index]
            
            price_info = {
                "flightNo": flightNo,
                "economy_origin": economy_origin_price,
                "economy_tax": economy_tax_price,
                "economy_total": economy_total_price,
                "economy_full": economy_full_price,
                "bussiness_origin": bussiness_origin_price,
                "bussiness_tax": bussiness_tax_price,
                "bussiness_total": bussiness_total_price,
                "bussiness_full": bussiness_full_price,
            }

            # self.prices=self.prices.append(price_info,ignore_index=True)
            self.prices = pd.concat(
                [self.prices, pd.DataFrame(price_info, index=[0])], ignore_index=True
            )

    def mergedata(self):
        try:
            self.df = self.flights.merge(self.prices, on=["flightNo"])
            print(f"合并后的航班数据形状: {self.df.shape}")
            print(f"合并后的航班数据列: {self.df.columns}")

            self.df["dateGetTime"] = dt.now().strftime("%Y-%m-%d")

            print(f"获取到的舒适度数据: {self.comfort_data}")
            
            # 数据的列名映射
            columns = {
                "dateGetTime": "数据获取日期",
                "flightNo": "航班号",
                "marketAirlineName": "航空公司",
                "departureday": "出发日期",
                "departuretime": "出发时间",
                "arrivalday": "到达日期",
                "arrivaltime": "到达时间",
                "duration": "飞行时长",
                "departureCountryName": "出发国家",
                "departureCityName": "出发城市",
                "departureAirportName": "出发机场",
                "departureAirportCode": "出发机场三字码",
                "arrivalCountryName": "到达国家",
                "arrivalCityName": "到达城市",
                "arrivalAirportName": "到达机场",
                "arrivalAirportCode": "到达机场三字码",
                "aircraftName": "飞机型号",
                "aircraftSize": "飞机尺寸",
                "aircraftCode": "飞机型号三字码",
                "arrivalPunctuality": "到达准点率",
                "stopCount": "停留次数",
                "stopInfo": "中转信息"
            }
            
            # 定义舒适度数据的列名映射
            comfort_columns = {
                'departure_delay_time': '出发延误时间',
                'departure_bridge_rate': '出发廊桥率',
                'arrival_delay_time': '到达延误时间',
                'plane_type': '飞机类型',
                'plane_width': '飞机宽度',
                'plane_age': '飞机机龄',
                'Y_has_meal': '经济舱是否有餐食',
                'Y_seat_tilt': '经济舱座椅倾斜度',
                'Y_seat_width': '经济舱座椅宽度',
                'Y_seat_pitch': '经济舱座椅间距',
                'Y_meal_msg': '经济舱餐食信息',
                'Y_power': '经济舱电源',
                'C_has_meal': '商务舱是否有餐食',
                'C_seat_tilt': '商务舱座椅倾斜度',
                'C_seat_width': '商务舱座椅宽度',
                'C_seat_pitch': '商务舱座椅间距',
                'C_meal_msg': '商务舱餐食信息',
                'C_power': '商务舱电源',
            }
            
            if self.comfort_data:
                comfort_df = pd.DataFrame.from_dict(self.comfort_data, orient='index')
                comfort_df.reset_index(inplace=True)
                comfort_df.rename(columns={'index': 'flight_no'}, inplace=True)
                
                print(f"舒适度数据形状: {comfort_df.shape}")
                print(f"舒适度数据列: {comfort_df.columns}")
                print(f"舒适度数据前几行: \n{comfort_df.head()}")
                
                # 检查 operateFlightNo 列是否存在
                if 'operateFlightNo' in self.df.columns:
                    print(f"合并前的 operateFlightNo 唯一值: {self.df['operateFlightNo'].unique()}")
                    # 创建一个临时列来存储用于匹配的航班号
                    self.df['match_flight_no'] = self.df['operateFlightNo'].fillna(self.df['flightNo'])
                else:
                    print("警告: operateFlightNo 列不存在于数据中,将使用 flightNo 进行匹配")
                    self.df['match_flight_no'] = self.df['flightNo']
                
                print(f"现有的列: {self.df.columns}")
                print(f"合并前的 flight_no 唯一值: {comfort_df['flight_no'].unique()}")
                
                # 使用 left join 来合并数据
                self.df = self.df.merge(comfort_df, left_on='match_flight_no', right_on='flight_no', how='left')
                
                print(f"合并后的数据形状: {self.df.shape}")
                print(f"合并后的数据列: {self.df.columns}")
                
                # 删除临时列和多余的flight_no列
                self.df.drop(['match_flight_no', 'flight_no'], axis=1, inplace=True, errors='ignore')
            else:
                # 如果没有舒适度数据，手动添加空列，保证数据结构一致性
                for col in comfort_columns.keys():
                    self.df[col] = None  # 添加缺失的舒适度列并填充为空值

            if rename_col:
                order = list(columns.values())
                # 对pandas的columns进行重命名
                columns.update(comfort_columns, errors='ignore')

                self.df = self.df.rename(columns=columns)

                if del_info:
                    # 使用 reindex 确保所有列都存在于最终的 DataFrame 中，不存在的列会被自动忽略
                    self.df = self.df.reindex(columns=order, fill_value=None)

            files_dir = os.path.join(
                os.getcwd(), self.date, dt.now().strftime("%Y-%m-%d")
            )

            if not os.path.exists(files_dir):
                os.makedirs(files_dir)

            filename = os.path.join(
                files_dir, f"{self.city[0]}-{self.city[1]}.csv")

            self.df.to_csv(filename, encoding="UTF-8", index=False)
            append_result_file(filename)

            print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 数据爬取完成 {filename}\n')

            return 0

        except Exception as e:
            print(f"合并数据失败 {str(e)}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            import traceback
            print(f"错误堆栈: {traceback.format_exc()}")
            return 0

    def capture_flight_comfort_data(self):
        try:
            # 滚动页面到底部以加载所有内容
            last_height = self.driver.execute_script("return document.body.scrollHeight")
            while True:
                # 分步滚动页面
                for i in range(10):  # 将页面分成10步滚动
                    scroll_height = last_height * (i + 1) / 3
                    self.driver.execute_script(f"window.scrollTo(0, {scroll_height});")
                    time.sleep(0.5)  # 每一小步等待0.5秒
                
                # 等待页面加载
                time.sleep(3)  # 滚动到底部后多等待3秒
                
                # 计算新的滚动高度并与最后的滚动高度进行比较
                new_height = self.driver.execute_script("return document.body.scrollHeight")
                if new_height == last_height:
                    break
                last_height = new_height

            comfort_requests = self.driver.requests
            comfort_data = {}
            batch_comfort_found = False
            getFlightComfort_requests_count = 0
            total_requests_count = len(comfort_requests)

            print(f"\n{time.strftime('%Y-%m-%d_%H-%M-%S')} 开始分析请求，总请求数：{total_requests_count}")

            for request in comfort_requests:
                if "/search/api/flight/comfort/batchGetComfortTagList" in request.url:
                    batch_comfort_found = True
                    print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 找到 batchGetComfortTagList 请求")
                    continue
                
                if "/search/api/flight/comfort/getFlightComfort" in request.url:
                    getFlightComfort_requests_count += 1
                    print(f"\n{time.strftime('%Y-%m-%d_%H-%M-%S')} 捕获到第 {getFlightComfort_requests_count} 个 getFlightComfort 请求:")
                    print(f"URL: {request.url}")
                    
                    try:
                        payload = json.loads(request.body.decode('utf-8'))
                        flight_no = payload.get('flightNoList', ['Unknown'])[0]
                        print(f"请求的航班号: {flight_no}")
                    except Exception as e:
                        print(f"无法解析请求 payload: {str(e)}")
                        continue

                    if request.response:
                        print(f"响应状态码: {request.response.status_code}")
                        body = request.response.body
                        if request.response.headers.get('Content-Encoding', '').lower() == 'gzip':
                            body = gzip.decompress(body)
                        
                        try:
                            json_data = json.loads(body.decode('utf-8'))
                            print(f"响应数据: {json.dumps(json_data, indent=2, ensure_ascii=False)[:500]}...")  # 打印前500个字符
                            if json_data['status'] == 0 and json_data['msg'] == 'success':
                                flight_comfort = json_data['data']
                                
                                punctuality = flight_comfort['punctualityInfo']
                                plane_info = flight_comfort['planeInfo']
                                cabin_info = {cabin['cabin']: cabin for cabin in flight_comfort['cabinInfoList']}
                                
                                processed_data = {
                                    'departure_delay_time': punctuality.get("departureDelaytime", None),
                                    'departure_bridge_rate': punctuality.get("departureBridge", None),
                                    'arrival_delay_time': punctuality.get("arrivalDelaytime", None),
                                    'plane_type': plane_info.get("planeTypeName", None),
                                    'plane_width': plane_info.get("planeWidthCategory", None),
                                    'plane_age': plane_info.get("planeAge", None)
                                }
                                
                                for cabin_type in ['Y', 'C']:
                                    if cabin_type in cabin_info:
                                        cabin = cabin_info[cabin_type]
                                        processed_data.update({
                                            f'{cabin_type}_has_meal': cabin['hasMeal'],
                                            f'{cabin_type}_seat_tilt': cabin['seatTilt']['value'],
                                            f'{cabin_type}_seat_width': cabin['seatWidth']['value'],
                                            f'{cabin_type}_seat_pitch': cabin['seatPitch']['value'],
                                            f'{cabin_type}_meal_msg': cabin['mealMsg']
                                        })
                                        if 'power' in cabin:
                                            processed_data[f'{cabin_type}_power'] = cabin['power']
                                
                                comfort_data[flight_no] = processed_data
                                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 成功提取航班 {flight_no} 的舒适度数据")
                            else:
                                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} getFlightComfort 响应状态异常: {json_data['status']}, {json_data['msg']}")
                        except Exception as e:
                            print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 处理 getFlightComfort 响应时出错: {str(e)}")
                    else:
                        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} getFlightComfort 请求没有响应")

            print(f"\n{time.strftime('%Y-%m-%d_%H-%M-%S')} 请求分析完成")
            print(f"总请求数: {total_requests_count}")
            print(f"batchGetComfortTagList 请求是否找到: {batch_comfort_found}")
            print(f"getFlightComfort 请求数: {getFlightComfort_requests_count}")
            print(f"成功提取的舒适度数据数: {len(comfort_data)}")

            if comfort_data:
                # 创建舒适度DataFrame
                comfort_df = pd.DataFrame.from_dict(comfort_data, orient='index')
                comfort_df.reset_index(inplace=True)
                comfort_df.rename(columns={'index': 'flight_no'}, inplace=True)
                
                # 保存舒适度数据为CSV文件
                # save_dir = os.path.join(os.getcwd(), self.date, datetime.now().strftime("%Y-%m-%d"))
                # os.makedirs(save_dir, exist_ok=True)
                
                # comfort_filename = os.path.join(save_dir, f"{self.city[0]}-{self.city[1]}_comfort.csv")
                # comfort_df.to_csv(comfort_filename, encoding="UTF-8", index=False)
                # print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 航班舒适度数据已保存到 {comfort_filename}")
                
                return comfort_data
            else:
                print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 未捕获到任何 getFlightComfort 数据")
                print("可能的原因:")
                print("1. 网页没有加载完全")
                print("2. 网站结构可能已经改变")
                print("3. 网络连接问题")
                print("4. 请求被网站拦截或限制")
                return None

        except Exception as e:
            print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} 捕获 getFlightComfort 数据时出错：{str(e)}")
            print(f"错误类型: {type(e).__name__}")
            print(f"错误详情: {str(e)}")
            import traceback
            print(f"错误堆栈: {traceback.format_exc()}")
            return None


def run_queries(citys=None, date_pairs=None):
    driver = init_driver()

    if citys is None:
        citys = crawl_routes

    if date_pairs is None:
        date_pairs = generate_round_trip_dates(begin_date, end_date, min_stay_days, days_interval)

    print(
        f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 本轮计划查询：{len(citys)} 条航线，{len(date_pairs)} 个往返日期组合，共 {len(citys) * len(date_pairs)} 组'
    )

    Flight_DataFetcher = DataFetcher(driver)

    for city in citys:
        Flight_DataFetcher.city = city

        for depart_date, return_date in date_pairs:
            Flight_DataFetcher.date = depart_date
            Flight_DataFetcher.return_date = return_date

            output_file = result_file_path(city, depart_date, return_date)
            if os.path.exists(output_file):
                existing_df = pd.read_csv(output_file)
                has_success = "状态" in existing_df.columns and (existing_df["状态"] == "成功").any()
                has_price = (
                    "往返含税价" in existing_df.columns
                    and existing_df["往返含税价"].notna().any()
                    and (existing_df["往返含税价"].astype(str) != "").any()
                )
                if has_success and has_price:
                    existing_file = output_file
                    append_result_file(existing_file)
                    print(
                        f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 成功结果文件已存在:{existing_file}')
                    continue
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 已存在文件不是成功结果，将重新查询:{output_file}')
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 当前的URL是：{driver.current_url}')
            try:
                Flight_DataFetcher.get_page(1)
            except Exception as e:
                error_message = f"查询异常：{type(e).__name__}, {str(e).split('Stacktrace:')[0].strip()}"
                print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} {city[0]}-{city[1]} {depart_date}-{return_date} {error_message}')
                Flight_DataFetcher.records = [Flight_DataFetcher.build_no_result_record(error_message)]
                Flight_DataFetcher.write_roundtrip_data()

            if not os.path.exists(output_file):
                print(
                    f'{time.strftime("%Y-%m-%d_%H-%M-%S")} {city[0]}-{city[1]} {depart_date}-{return_date} 未生成结果文件，写入失败记录'
                )
                Flight_DataFetcher.records = [Flight_DataFetcher.build_no_result_record("页面查询未生成结果")]
                Flight_DataFetcher.write_roundtrip_data()

            time.sleep(crawl_interval)

    # 运行结束退出
    try:
        driver = Flight_DataFetcher.driver
        driver.quit()
    except Exception as e:
        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} An error occurred while quitting the driver: {e}')

    combined_file = write_combined_results(result_files)
    if combined_file:
        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 汇总文件已生成：{combined_file}')

    if send_email_after_run and combined_file:
        try:
            send_result_email([combined_file])
        except Exception as e:
            print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 机票结果邮件发送失败：{type(e).__name__}, {e}')
    else:
        print(f'{time.strftime("%Y-%m-%d_%H-%M-%S")} 邮件自动发送已关闭，请先向 lyx 展示邮件预览和附件清单')

    print(f'\n{time.strftime("%Y-%m-%d_%H-%M-%S")} 程序运行完成！！！！')

    return combined_file


def open_manual_login():
    driver = init_driver()
    try:
        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 正在打开携程机票页面", flush=True)
        driver.set_page_load_timeout(max_wait_time * 2)
        driver.get("https://flights.ctrip.com/online/channel/domestic")
        print(f"{time.strftime('%Y-%m-%d_%H-%M-%S')} manual_login: 携程机票页面已打开", flush=True)
        fetcher = DataFetcher(driver)
        fetcher.wait_for_manual_login()
    finally:
        driver.quit()


def main():
    return run_queries()


if __name__ == "__main__":
    main()
