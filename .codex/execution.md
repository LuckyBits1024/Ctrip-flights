# 执行记录

## 2026-05-13 初始调研
- 读取根目录 `README.md` 与 `requirements.txt`。
- 读取 `Linux_version/readme.md` 与 `Linux_version/requirements.txt`，确认 Linux 版本重点是 IPv6 SOCKS5 代理，不作为 Windows 当前入口。
- 读取 `ctrip_flights_scraper_V3.py` 头部和尾部，确认主入口、Edge WebDriver、默认采集配置与登录/验证码风险。
- 读取 `csv_to_xlsx_converter.py`，确认它是 CSV 合并到 XLSX 的后处理脚本。
- 使用绕开 profile 的 PowerShell 检查 Python 路径，发现系统同时存在 Anaconda、Python 3.7、Python 2.7、MSYS Python。

## 2026-05-13 修复 conda 环境前缀
- 提升权限后运行 `conda env list` 成功，确认存在 `ctrip` 环境。
- 在 `ctrip` 中执行 Python 发现：
  - `sys.executable = D:\anaconda3\envs\ctrip\python.exe`
  - `sys.prefix = D:\anaconda3\envs`
  - `sys.base_prefix = D:\anaconda3\envs\pytorch`
  - `sys.path` 加载 `D:\anaconda3\envs\pytorch\DLLs`、`D:\anaconda3\envs\pytorch\lib`、`D:\anaconda3\envs\lib\site-packages`
- 找到父目录配置文件 `D:\anaconda3\envs\pyvenv.cfg`，内容指向 `D:\anaconda3\envs\pytorch`。
- 将该文件改名备份为 `D:\anaconda3\envs\pyvenv.cfg.bak-codex-20260513`，未删除。
- 复验 `ctrip`：
  - `sys.prefix = D:\anaconda3\envs\ctrip`
  - `sys.base_prefix = D:\anaconda3\envs\ctrip`
  - `unicodedata` 导入成功
  - `pip 26.1.1 from D:\anaconda3\envs\ctrip\lib\site-packages\pip (python 3.10)`

## 2026-05-13 目标变更
- lyx 要求实际运行项目，自助解决运行问题，直到获取上海出发到香港、9 月 25 日到 10 月 7 日的机票价格。
- lyx 要求将获取到的机票信息发送到指定邮箱。
- 邮箱凭据由 lyx 在会话中提供；执行记录不写入明文授权码。

## 2026-05-13 依赖与脚本配置
- `requirements.txt` 增加 `setuptools==80.9.0`，原因是 `selenium-wire==5.1.0` 依赖 `pkg_resources`，而当前 `setuptools 82.0.1` 已移除该模块。
- 重新安装 `requirements.txt` 成功。
- 核心依赖导入成功：`magic`、`pandas`、`seleniumwire`、`selenium`、`blinker`。
- Edge WebDriver 验证成功：浏览器为 Microsoft Edge 148.0.3967.54。
- `ctrip_flights_scraper_V3.py` 已改为只采集上海 -> 香港，日期为 2026-09-25 至 2026-10-07，共 13 天。
- 增加结果邮件发送功能，程序结束后统一发送本轮 CSV 附件；授权码按 lyx 允许写入代码，但不写入执行记录明文。
- 修复明显运行错误：
  - Selenium 复合 class 选择器改为 CSS selector。
  - 验证码输入从列表对象修正为输入字符串。
  - JSON 解码分支给 `self.dedata` 正确赋值。
- `python -m py_compile ctrip_flights_scraper_V3.py` 通过。

## 2026-05-13 降低刷新频率与 SeleniumWire 修复
- lyx 要求刷新频率低一些。
- 将 `crawl_interval` 调整为 30 秒，`max_retry_time` 调整为 3，新增 `retry_wait_time = 30`。
- 修复 `get_page()` 异常后递归快速刷新问题：失败后至少等待 30 秒，最多 3 次，并在浏览器窗口关闭时避免继续读取 URL 造成异常递归。
- 单测普通 Selenium 访问携程首页成功。
- 单测 SeleniumWire 访问携程首页初始失败，根因是 `pyOpenSSL 26.2.0` / `cryptography 48.0.0` 与 `selenium-wire==5.1.0` 内置 mitmproxy 不兼容。
- `requirements.txt` 增加 `pyOpenSSL==24.2.1`、`cryptography==43.0.3`，安装后 `X509.get_extension` 可用。
- SeleniumWire 在 `options.page_load_strategy = "eager"` 下访问携程首页成功。
# 2026-05-13 调研阶段
- 已创建/复用 `.codex/` 过程目录。
- 已读取 `README.md`、`Linux_version/readme.md`、`requirements.txt`、`ctrip_flights_scraper_V3.py` 关键片段。
- 已读取本地 `lark-mail` 与 `lark-shared` skill 的关键规则：邮件写操作优先 user 身份；实际发送前必须展示收件人、主题、正文摘要并获得用户确认。
- 发现当前主脚本配置与本轮目标不一致：路线仍为上海到香港，结束日期为 `2026-10-07`，且 `check_data()` 会无条件删除中转航班。
- 已将本轮调研结果写入 `.codex/discovery.md`，状态写入 `.codex/progress.md`，计划草案写入 `.codex/plan.md`。

# 2026-05-13 本机环境补充调研
- 继续读取 `ctrip_flights_scraper_V3.py` 主流程，确认 `get_page()` 当前固定点击“单程”，如要查询往返价格需要改页面模式、日期输入与输出解析。
- 检查本机 Python：默认 `python3` 为 `/opt/homebrew/bin/python3`，版本 `3.14.4`。
- 检查 uv：已安装，且本机已有 uv Python `3.12.13`、`3.11.15`、`3.13.12`、`3.14.4`。建议后续用 uv Python `3.12.13` 创建项目内 `.venv`，但需 lyx 确认。
- 检查浏览器：未发现 Microsoft Edge；已安装 Google Chrome `143.0.7499.110`；未发现 `chromedriver` / `msedgedriver` 命令。
- 已更新 `.codex/discovery.md`、`.codex/progress.md`、`.codex/plan.md`、`.codex/session-handoff.md`。
- 未修改业务代码，未安装依赖，未发起携程查询，未发送邮件。

# 2026-05-13 lyx 部分确认记录
- lyx 确认日期范围为 `2026-09-25` 至 `2026-10-10`。
- lyx 确认目的地城市为：伦敦、巴黎、法兰克福、阿姆斯特丹、马德里、罗马、米兰、慕尼黑、苏黎世、维也纳、伊斯坦布尔、赫尔辛基、哥本哈根、巴塞罗那、布鲁塞尔、都柏林、布拉格、雅典、里斯本、斯德哥尔摩、奥斯陆、华沙。
- lyx 确认要查往返价格。
- lyx 允许脚本从 Edge 改为 Chrome。
- lyx 允许最终用 `1264932425@qq.com` 发给 `1264932425@qq.com`；实际发送前仍需邮件预览确认。
- 待确认：往返回程日期规则；是否允许用 uv Python `3.12.13` 创建项目内 `.venv`。

# 2026-05-13 lyx 补充确认记录
- lyx 说明往返需求不是固定某天进出，而是出发日期在 `2026-09-25` 至 `2026-10-10` 期间，查询往返中间相差 9 天以上的所有航班组合。
- lyx 明确允许使用 uv 的 Python `3.12.13` 创建项目内 `.venv`。
- 待确认：回程日期枚举上界，当前不能确定是否也限制在 `2026-09-25` 至 `2026-10-10` 内，或允许晚于 `2026-10-10`。

# 2026-05-13 回程上界确认
- lyx 确认回程日期指“回程出发日期”，不是到达日期。
- lyx 确认回程出发日期不可以晚于 `2026-10-10`。
- 由此生成规则确定为：去程出发日期和回程出发日期均在 `2026-09-25` 至 `2026-10-10` 内，且相差至少 9 天。
- 计算规模：28 个往返日期组合，22 个目的地，共 616 个目的地/日期组合。

# 2026-05-13 环境配置与只读审阅
- 已使用 uv Python `3.12.13` 创建项目内 `.venv`。
- 已使用 `uv pip install --python .venv/bin/python -r requirements.txt` 将依赖安装到 `.venv`。
- `.venv/bin/python` 版本为 Python `3.12.13`。
- 初次导入校验发现 `python-magic` 找不到系统 `libmagic`；本机未发现 `/opt/homebrew/opt/libmagic/lib` 和 `/opt/homebrew/lib/libmagic*.dylib`。
- Chrome WebDriver 最小启动验证通过，浏览器版本为 Chrome `143.0.7499.110`。
- 只读子 Agent 审阅结论：当前 `init_driver()` 固定 Edge；`get_page()` 固定单程；`change_city()` 只有一个日期；`get_data()` 只校验 `flightSegments[0]`；`proc_flightSegments()` 只取第一个航段第一段 flightList；`proc_priceList()` 用 `itineraryId.split("_")[0]` 合并价格，往返/中转下有错配风险。

# 2026-05-13 单组合试跑 1
- 试跑范围：上海 -> 伦敦，去程 `2026-09-25`，回程出发 `2026-10-04`。
- 试跑结果：未生成 CSV。
- 观察到脚本可以打开 Chrome、进入携程首页、确认页面为往返查询、将目的地改到 `伦敦(英国)(LON)`、将去程/返程日期改到目标值。
- 失败原因：`change_city()` 在结果页继续查找首页的 `.search-btn`，导致 `NoSuchElementException`；这不是登录问题。
- 额外问题：失败分支在 `max_retry_time=1` 时仍会 `get_page(1)`，造成短时间快速重试，需要收敛。

# 2026-05-13 单组合试跑 2
- 修复：去掉结果页二次查找 `.search-btn`；请求校验从严格匹配 `伦敦` 改为接受携程返回的 `伦敦(英国)`。
- 试跑范围：上海 -> 伦敦，去程 `2026-09-25`，回程出发 `2026-10-04`。
- 观察到正确的往返请求体：去程 `上海 -> 伦敦(英国)`、`2026-09-25`；返程 `伦敦(英国) -> 上海`、`2026-10-04`。
- 试跑仍未生成 CSV。
- 当前阻塞：第三次试跑出现携程登录弹窗 `lg_loginbox_modal`，覆盖目的地输入框，说明后续需要先完成携程网页登录。当前脚本内携程账号密码为空，无法自动登录。

# 2026-05-13 手动登录
- 已添加手动网页登录流程：打开 Chrome 等待 lyx 登录携程，检测到登录完成后保存 cookies。
- 已将 `.venv/`、`cookies.json`、`results/` 加入 `.gitignore`，避免误提交虚拟环境、登录 cookies 和结果文件。
- 已启动 Chrome 并完成一次手动登录检测。
- 脚本保存了 16 条携程 cookies 到 `cookies.json`；过程文件不记录 cookie 值。

# 2026-05-13 往返接口结构确认
- 接口结构探针范围：上海 -> 伦敦，去程 `2026-09-25`，回程出发 `2026-10-04`。
- 已确认 `flightItineraryList` 可返回报价，示例返回 69 条 itinerary。
- 当前首轮响应中 `flightItineraryList[*].flightSegments` 只有 1 段航班明细；但 `priceList[*].priceUnitList[*].flightSeatList` 中出现 `segmentNo` 1 和 2，说明价格为往返总价。
- lyx 确认先完成首轮响应的往返价格查询和 CSV 落盘，再研究回程明细展开。

# 2026-05-13 lyx 新增排序要求
- lyx 提供页面截图并要求：选择去程和选择返程时都要选“低价优先”。
- 后续需要定位排序按钮和选择航班的 UI 结构，修改流程为去程低价优先、返程低价优先。

# 2026-05-13 低价优先 UI 结构确认
- 单组合 UI 探针确认：“低价优先”按钮为 `li.sort-item.ticket-price`。
- 去程低价优先后，第一条航班按钮文案为“选为去程”。
- 点击“选为去程”后进入“选择返程”页；返程低价优先后，第一条航班按钮文案为“订票”。
- 已调整正式流程：搜索后选择去程低价优先，读取第一条去程并点击“选为去程”；进入返程后选择低价优先，读取第一条返程及往返含税价；不点击“订票”。

# 2026-05-13 lyx 低价优先要求收敛
- lyx 再次明确：选择去程和选择返程时都要选“低价优先”。
- 已检查正式流程：`collect_low_price_roundtrip_from_page()` 在去程和返程两个阶段分别调用 `select_low_price_sort()`。
- 已收紧 `select_low_price_sort()`：如按钮未选中则点击，并等待 `li.sort-item.ticket-price` 进入 `active` 状态后再读取航班。
- 已收紧首条航班等待逻辑为 Selenium 标准 locator 等待。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py` 通过。

# 2026-05-13 巴黎 28 组试跑中断处理
- 低频试跑巴黎 28 个日期组合时，已有成功文件会跳过。
- 新增成功结果：`2026-09-25` -> `2026-10-05`、`2026-09-25` -> `2026-10-06`、`2026-09-26` -> `2026-10-05`。
- 试跑在 `2026-09-26` -> `2026-10-06` 组合等待去程“低价优先”按钮时超时，中断了整轮流程。
- 已修改 `run_queries()`：每个日期组合单独捕获异常，写入失败记录 CSV 后继续下一组；如果内部捕获错误但未生成 CSV，也补写“页面查询未生成结果”。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py` 通过。

# 2026-05-13 首页等待时间调整
- 重跑巴黎时发现首页控件有时超过 10 秒才挂载，过短等待会误写失败记录。
- 已停止该轮试跑，避免继续产生低质量失败结果。
- 已将 `max_wait_time` 从 `10` 调整为 `60`，不增加额外兜底层，只延长页面控件等待时间以配合低频执行。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py` 通过。

# 2026-05-13 验证码/风控触发后暂停
- lyx 指出继续调试已触发携程验证码/风控。
- 已立即停止后续自动化查询，不再继续全量或重跑失败项。
- 已只读确认当前没有残留 `.venv/bin/python` 查询进程，也没有 `chromedriver` 自动化进程。
- 约束：不得代解验证码；后续必须等待 lyx 指示或手动处理后再继续。

# 2026-05-13 恢复执行
- lyx 要求“开始吧”。
- 当前策略：先只补巴黎剩余/失败组合，间隔 `120` 秒，结果页最多等待 `180` 秒；若再次出现验证码/风控，立即停止。

# 2026-05-13 巴黎低频补跑结果
- 低频补跑成功覆盖：
  - `2026-09-28` -> `2026-10-08`
  - `2026-09-28` -> `2026-10-09`
- 后续连续两次首页控件在 60 秒内未挂载，已中断执行，避免继续误写失败结果或加重风控。
- 已只读确认没有残留 `.venv/bin/python` 查询进程，也没有 `chromedriver` 自动化进程。
- 巴黎 28 组当前状态：21 组成功，2 组失败，5 组未跑。

# 2026-05-13 正式 runner 收敛
- 已新增 `run_flight_job.py`，作为正式脚本队列入口；后续由 runner 启动脚本，不再用 agent 临场诊断页面。
- 已将验证码/风控检测改为记录 `captcha_detected=True` 并停止当前自动化，不再等待人工输入验证码。
- 编译验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过。
- 启动 runner 时发现当前 `results/` 目录内没有此前生成的巴黎 CSV，只剩 `.DS_Store`；全局搜索未找到 `*巴黎*.csv` 或汇总 CSV。
- 因结果文件缺失，runner 认为巴黎 28 组全部待跑。已中断 runner，未继续重跑。

# 2026-05-13 全量重跑准备
- lyx 要求“全部重新重跑”。
- 已为 `run_flight_job.py` 增加 `--force`，可忽略已有成功结果重新执行全部任务。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过。

# 2026-05-13 开口程需求实现
- lyx 新增需求：支持异地返程/开口程，例如去程 `上海 -> 巴黎`，返程 `米兰 -> 上海`。
- lyx 确认价格口径选方案 2：使用携程“多程/开口程产品价”，不是两段单程相加。
- 已新增开口程结果路径：
  - raw：`results/<日期范围>/<运行日期>/open_jaw/raw/上海-巴黎__米兰-上海_<去程日期>_return_<回程日期>.csv`
  - group：`results/<日期范围>/<运行日期>/open_jaw/上海-巴黎__米兰-上海.csv`
- group CSV 会汇总同一组“去程目的地 + 返程出发地”的全部日期组合，并按 `往返含税价` 从高到低排序。
- `run_flight_job.py` 新增 `--open-jaw OUTBOUND_DESTINATION RETURN_DEPARTURE_CITY` 参数，例如 `--open-jaw 巴黎 米兰`。
- 非网络验证：
  - `.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过。
  - `build_open_jaw_tasks([['巴黎', '米兰']], force=True)` 生成 28 个日期组合任务。

# 2026-05-13 子 Agent 调度补齐
- lyx 指出此前子 Agent 调度不足。
- 已实际派发两个只读子 Agent：
  - 子 Agent A：审阅 `ctrip_flights_scraper_V3.py` 与 `run_flight_job.py` 的 open_jaw/多程 UI、runner 参数、验证码/连续失败停机逻辑。
  - 子 Agent B：审阅 CSV 输出契约、open_jaw raw/group 路径、价格降序排序、`.gitignore` 与敏感文件/结果文件边界。
- 两个子 Agent 均被明确要求不运行浏览器、不访问携程、不修改文件、不提交或推送。
- 主 Agent 已同步收敛 `.gitignore`，忽略 `.DS_Store`、`.codex/flight_job.log`、`.codex/flight_job_status.json`。

# 2026-05-13 子 Agent 反馈修复
- 子 Agent A/B 均已返回只读审阅结果，未运行浏览器、未访问携程、未修改文件。
- 已修复 open_jaw request 匹配：`query_mode == "open_jaw"` 时第二段匹配 `return_departure_city -> 上海`，不再按普通往返的 `目的地 -> 上海` 判断。
- 已修复开口程价格口径风险：不再使用第一程价格兜底；第二程页面未读到价格时写入 `未读到开口程产品含税价` 失败记录。
- 已统一 open_jaw CSV schema：成功/失败 raw CSV 和 group CSV 都使用固定列，失败记录补齐 `往返含税价`、`开口程含税价`、展示信息等字段。
- 已修复 group CSV 生成时机：runner 在无待执行 open_jaw 任务、每次 raw 成功后、任务结束时都会刷新对应 group CSV。
- 已固定本轮输出日期目录：runner 启动时设置 `result_run_day`，避免长任务跨午夜将 raw/group 分到不同日期目录。
- 已让 runner 区分 `无航班结果` 和技术失败，业务无结果不再计入连续失败停机。
- 验证：
  - `.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过。
  - `.venv/bin/python run_flight_job.py --help` 正常展示 `--open-jaw` 参数。
  - 离线验证 `build_open_jaw_tasks([['巴黎', '米兰']], force=True)` 生成 28 个日期组合。
  - 在 `/private/tmp` 构造 open_jaw raw CSV 后调用 `write_open_jaw_group_results('巴黎', '米兰')`，确认 group CSV 按 `往返含税价` 从高到低排序且列顺序等于 `OPEN_JAW_COLUMNS`。
- 未执行真实携程查询，未打开浏览器，未发送邮件，未提交或推送。

# 2026-05-13 开口程单组真实试跑
- 试跑命令：`.venv/bin/python run_flight_job.py --open-jaw 巴黎 米兰 --force --limit 1 --interval 300 --max-wait 90 --max-search-wait 120 --max-consecutive-failures 1`。
- 试跑目标：`上海 -> 巴黎 / 米兰 -> 上海`，去程 `2026-09-25`，回程 `2026-10-04`。
- 调试中确认并修复：
  - 新版携程多程入口文本为 `多程(含缺口程)`。
  - 多程城市输入使用 `.form-input-v2`，name 为 `mtDCity1/mtACity1/mtDCity2/mtACity2`。
  - macOS Chrome 下输入框清空需使用 `Command+A`。
  - 新版日期格为 `.date-day`，不是旧版 `.date`。
  - 结果页选择第一程后没有旧版 `.segment_tab.active`，应等待页面出现“第二程”，再读取带 `订票` 的第二程航班卡片。
- 最终试跑结果：成功。
- 生成结果：
  - raw CSV：`results/2026-09-25_to_2026-10-10/2026-05-13/open_jaw/raw/上海-巴黎__米兰-上海_2026-09-25_return_2026-10-04.csv`
  - group CSV：`results/2026-09-25_to_2026-10-10/2026-05-13/open_jaw/上海-巴黎__米兰-上海.csv`
- 结果摘要：状态 `成功`，排序方式 `第一程低价优先；第二程低价优先`，多程含税价 `9925`。
- 去程展示：`中国国航 CA1566 / CA933`，上海虹桥 T2 出发，转北京，到巴黎戴高乐 T1。
- 回程展示：`中国国航 CA968`，米兰马尔彭萨 T1 到上海浦东 T2。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过。
- 未发送邮件，未 commit，未 push。
## 2026-05-13 23:45 全量同城往返查询启动
- 按 lyx 最新要求，改为用正式脚本自主执行全量查询，我只读取 stdout、状态文件和 CSV 结果，不再手工介入页面流程。
- 启动命令：`.venv/bin/python run_flight_job.py --all-cities --interval 180 --max-wait 90 --max-search-wait 180 --max-consecutive-failures 5`
- 查询范围：上海出发，22 个欧洲目的地，同城往返；去程出发 `2026-09-25` 至 `2026-10-10`，回程出发不晚于 `2026-10-10`，停留至少 9 天。
- runner 启动时检测到已有 6 个伦敦成功结果，因此待执行为 610 组。
- 23:45 成功补跑 `上海-伦敦 2026-09-25 -> 2026-10-10`。
- 23:49 成功补跑 `上海-伦敦 2026-09-26 -> 2026-10-05`。

## 2026-05-13 入口封装与提交前验证
- lyx 要求封装函数主入口，不要把主程序调用放在脚本核心逻辑里。
- 已将 `run_flight_job.py` 的实际执行入口拆为 `run_flight_job(args)`，`main()` 只负责解析 CLI 参数并调用该函数。
- 已为 `ctrip_flights_scraper_V3.py` 增加 `main()`，底部仅保留 `if __name__ == "__main__": main()`，导入模块不会启动查询。
- 已验证：
  - `.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过。
  - `.venv/bin/python run_flight_job.py --help` 只展示 CLI 参数，不启动查询。
  - 导入 `run_flight_job` 与 `ctrip_flights_scraper_V3` 只检查到函数存在，不启动 Chrome。
- 提交前确认 `results/`、`cookies.json`、`.venv/` 均未纳入 Git。

## 2026-05-14 runner 技术失败恢复
- 提交后恢复全量查询，runner 从 608 个待执行组合继续。
- 已成功补跑 `上海-伦敦 2026-09-26 -> 2026-10-06`。
- 随后连续 5 组卡在首页控件等待，均属于技术失败，不是验证码，也不是业务无航班结果；runner 按阈值停止并生成汇总 CSV。
- 已修正 `run_flight_job.py`：遇到技术失败时明确记录并重启浏览器会话后继续下一组，避免同一个 Chrome 会话在失败后持续卡住。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过；`.venv/bin/python run_flight_job.py --help` 正常。
- 跨午夜后发现 runner 默认使用当天日期目录，误切到 `2026-05-14` 结果目录；已新增 `--run-day` 参数，后续继续查询时固定 `--run-day 2026-05-13`，复用原结果目录跳过已有成功结果。

## 2026-05-14 目的地口径更新
- lyx 最新要求：英国不纳入本次欧洲目的地范围。
- 已暂停仍包含伦敦的 runner，并从 `destination_citys` 移除 `伦敦`。
- 已生成的伦敦结果文件保留在 ignored 的 `results/` 中，不纳入提交；后续默认全量只跑 21 个非英国目的地。

## 2026-05-14 输出结构与频率调整
- lyx 要求：同一出发地和目的地的不同日期机票放在一个 CSV，不再生成一堆单日期过程文件。
- 已将普通往返结果路径改为航线级文件，例如 `上海-巴黎.csv`；每次查询同一日期组合时更新该航线文件中的对应行。
- 航线文件与总汇总文件均按价格升序排序；无法读取价格的记录排在最后。
- 查询间隔从固定 `180s` 改为 `30-60s` 随机等待，对应 CLI 参数为 `--min-interval` 和 `--max-interval`。
- 验证：`.venv/bin/python -m py_compile ctrip_flights_scraper_V3.py run_flight_job.py` 通过；`.venv/bin/python run_flight_job.py --help` 正常。
- 启动前检查 `results/` 下已经没有旧的单日期过程 CSV。
