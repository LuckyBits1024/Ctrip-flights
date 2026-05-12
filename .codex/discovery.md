# 调研记录

# README 环境要求
- 项目：Ctrip-Crawler，基于 Selenium 与 SeleniumWire 采集携程航班数据。
- Python 要求：Python 3.6 及以上。
- 安装命令：`pip install -r requirements.txt`。
- 浏览器驱动：根据 Chrome 或 Edge 下载并配置对应驱动，要求驱动版本与浏览器版本匹配。
- 启动命令：README 示例为 `python your_script_name.py`；本仓库 Windows 主脚本为 `ctrip_flights_scraper_V3.py`。

# 根目录依赖
- `pandas==2.2.3`
- `selenium_wire==5.1.0`
- `blinker==1.7.0`
- `python-magic==0.4.27; platform_system != "Windows"`
- `python-magic-bin==0.4.14; platform_system == "Windows"`

# 代码入口发现
- `ctrip_flights_scraper_V3.py` 为 Windows/Edge 版本主入口。
- `init_driver()` 默认使用 `webdriver.EdgeOptions()` 和 `webdriver.Edge(options=options)`。
- 默认未启用 headless；运行时会打开 Edge 浏览器。
- 默认采集城市为 `["上海", "香港", "东京"]`，默认采集未来 60 天、城市两两组合。
- `login_allowed = True`，但 `accounts` 和 `passwords` 为空字符串；运行过程中可能需要人工登录/验证码处理。
- `csv_to_xlsx_converter.py` 是后处理脚本，不是爬虫启动入口。
- `Linux_version/ctrip_flights_scraper_V3.5.py` 是 Linux/Chrome/headless/IPv6 代理版本，不适合作为当前 Windows 首选入口。

# 当前故障线索
- lyx 提供的错误：`pip install -r requirements.txt` 在 conda 环境 `ctrip` 中导入 `unicodedata` 失败，路径混入 `D:\anaconda3\envs\lib\site-packages`。
- 本机普通 PowerShell profile 中执行 conda hook 报“拒绝访问”，提示 conda 可执行或环境目录访问需要进一步验证。
- 该类错误通常不是项目依赖本身导致，而是 Python/conda 环境损坏、路径混乱或权限问题导致。

# 验收目标
- 能在一个明确的 Python 环境中成功执行 `python -m pip install -r requirements.txt`。
- 能成功导入项目依赖：`magic`、`pandas`、`seleniumwire`、`selenium`。
- 能启动 `ctrip_flights_scraper_V3.py` 到浏览器初始化/页面访问阶段，或明确停在需要 lyx 人工处理的账号、验证码、网络/驱动问题。
- 当前业务目标：采集上海 -> 香港，日期范围待确认为 2026-09-25 至 2026-10-07。
- 邮件目标：采集完成后发送到 lyx 指定邮箱；授权码不得写入仓库代码、上下文文件或日志。
