# 调研记录

# README 解析
- 项目名称：`Ctrip-Crawler`。
- 功能：基于 Selenium 与 SeleniumWire 模拟浏览器访问携程官网，捕获航班数据、票价数据并输出 CSV。
- 环境要求：Python 3.6 及以上。
- 安装方式：`pip install -r requirements.txt`。
- 浏览器驱动：根据 Chrome 或 Edge 配置对应 WebDriver，驱动版本需匹配浏览器版本。
- 启动方式：README 示例为 `python your_script_name.py`；本仓库根目录主脚本是 `ctrip_flights_scraper_V3.py`。
- 输出路径：`./<航班日期>/<当前日期>/<出发城市>-<目的城市>.csv`。

# 依赖清单
- `pandas==2.2.3`
- `selenium_wire==5.1.0`
- `blinker==1.7.0`
- `setuptools==80.9.0`
- `pyOpenSSL==24.2.1`
- `cryptography==43.0.3`
- `python-magic==0.4.27; platform_system != "Windows"`
- `python-magic-bin==0.4.14; platform_system == "Windows"`

# 代码入口与配置发现
- 入口文件：`ctrip_flights_scraper_V3.py`。
- 当前浏览器：`init_driver()` 默认使用 Edge：`webdriver.EdgeOptions()` 与 `webdriver.Edge(options=options)`。
- 当前运行模式：非 headless，会打开浏览器窗口，可能触发登录/验证码人工处理。
- 当前路线：`crawl_routes = [["上海", "香港"]]`。
- 当前日期：`begin_date = "2026-09-25"`，`end_date = "2026-10-07"`，`crawl_days = 13`。
- 当前是否直飞：`direct_flight = True`。
- 当前主流程：`get_page()` 会固定点击“单程”；如要查询携程往返价格，需要修改页面操作与数据解析范围。
- 当前输出：每个日期/路线输出一个 CSV，并把路径加入 `result_files`。
- 当前邮件逻辑：程序结束后调用 `send_result_email(result_files)`，以 CSV 附件发送邮件。
- 当前邮件配置已包含 QQ 邮箱 SMTP 字段；用户本轮提供的发件人与收件人均为同一个 QQ 邮箱，授权码不写入过程文件。

# 本机环境发现
- 当前默认 `python3`：`/opt/homebrew/bin/python3`，版本 `3.14.4`。
- 本机 uv 已安装：`/Users/bytedance/.local/bin/uv`。
- uv 已安装 Python：`3.14.4`、`3.13.12`、`3.12.13`、`3.11.15`、系统 `3.9.6`。
- 项目内尚未发现 `.venv` 或 `venv`。
- 已安装浏览器：Google Chrome `143.0.7499.110`。
- 未发现 `/Applications/Microsoft Edge.app`，且未发现 `chromedriver` / `msedgedriver` 命令。

# 与本轮任务的差距
- 目标应为上海出发到欧洲主要机场，而不是上海到香港。
- 目标日期应覆盖 `2026-09-25` 至 `2026-10-10`，共 16 天；当前结束日期少到 `2026-10-07`。
- 用户要求包括中转航班；当前 `check_data()` 无条件移除 `transferCount != 0` 的航班，需要改为保留中转航班。
- 用户同时写了“只查上海 -> 欧洲的单程出发方向”和“要查往返的 查看往返的价格”，这会影响页面模式、输入日期和输出字段，进入执行前必须确认。
- README 只描述城市/航线组合配置，没有直接按机场三字码配置；若要“主要机场”级别，需要确认是按欧洲城市查询后从结果机场筛选，还是只查指定机场所在城市。
- 需要在项目内创建虚拟环境，不能使用系统 Python。
- 邮件发送使用脚本内 QQ SMTP 配置；实际发送前必须展示收件人、主题、正文摘要和附件清单，并等待 lyx 明确确认。

# 初步建议的欧洲主要机场候选
以下是建议候选，需要 lyx 确认后才执行：
- 伦敦：LHR/LGW 所在城市查询入口为“伦敦”
- 巴黎：CDG/ORY 所在城市查询入口为“巴黎”
- 法兰克福：FRA，城市“法兰克福”
- 阿姆斯特丹：AMS，城市“阿姆斯特丹”
- 马德里：MAD，城市“马德里”
- 罗马：FCO，城市“罗马”
- 米兰：MXP/LIN，城市“米兰”
- 慕尼黑：MUC，城市“慕尼黑”
- 苏黎世：ZRH，城市“苏黎世”
- 维也纳：VIE，城市“维也纳”
- 伊斯坦布尔：IST/SAW，城市“伊斯坦布尔”
- 赫尔辛基：HEL，城市“赫尔辛基”
- 哥本哈根：CPH，城市“哥本哈根”

# 待 lyx 确认的问题
1. 日期是否确认为 `2026-09-25` 至 `2026-10-10`。
2. 欧洲主要机场范围是否采用上面的候选城市/机场；是否按“可以多一点”增加巴塞罗那、布鲁塞尔、都柏林、布拉格、雅典、里斯本、斯德哥尔摩、奥斯陆、华沙等城市。
3. 查询模式需要二选一确认：A. 只查上海到欧洲的单程价格；B. 查上海到欧洲并返回上海的往返价格。如果选 B，还需要确认回程日期或回程日期范围。
4. 是否允许我把脚本浏览器从 Edge 改为 Chrome；本机未发现 Edge，但已安装 Chrome。
5. 是否同意后续使用 uv 的 Python 3.12.13 在项目内创建 `.venv`。
6. 是否确认邮件最终发到并由 `1264932425@qq.com` 发出；实际发送前我会再给出邮件预览并等待确认。
