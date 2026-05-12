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
