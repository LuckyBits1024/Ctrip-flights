# 固定协作规则
- 所有回复必须以称呼 `lyx` 开头。
- 使用中文进行记录与回复。
- 遇到不确定的设计/实现问题，必须先问 lyx，不得擅自拍板。
- 除非 lyx 主动要求，不写兼容性代码、不写多层兜底、不隐藏日志。
- 临时 debug 探针 / 版本打印 / 路径探针仅限短期定位使用；问题确认解决后必须立即删除或收敛为必要检查，避免长期噪音。
- 未经 lyx 明确允许，禁止执行 `git commit`、`git push`；`rm -rf`、`git checkout --` 等高危操作必须先获得 lyx 同意。
- 上下文接近满、发生压缩、或需要切换到新 Agent 时，必须先生成交接摘要，再让下一个 Agent 接手；新 Agent 必须先读取交接摘要与上下文文件，禁止从头猜测。

# 当前目标
把 `D:\PythonProject\Ctrip-Crawler` 跑起来，获取上海出发到香港、9 月 25 日到 10 月 7 日的机票价格，并将获取结果发送到 lyx 指定邮箱。

# 已验证状态
- 已读取 `README.md`、`requirements.txt`、`Linux_version/readme.md`、`Linux_version/requirements.txt`。
- Windows 版 README 要求：Python 3.6+，安装根目录 `requirements.txt`，配置浏览器驱动，运行主脚本。
- 根目录依赖包含 Windows 条件依赖 `python-magic-bin==0.4.14`。
- 当前普通 PowerShell profile 调用 `D:\anaconda3\Scripts\conda.exe` 报“拒绝访问”；提升权限后 conda 可运行。
- 系统可见 Python：`D:\anaconda3\python.exe`、`C:\Program Files\Python37\python.exe`、`C:\Python27\python.exe`、`C:\msys64\mingw64\bin\python.exe`。
- 已确认 `D:\anaconda3\envs\pyvenv.cfg` 错误指向 `D:\anaconda3\envs\pytorch`，导致 `ctrip` 环境 `sys.prefix`/`sys.path` 串到 pytorch。
- 已将该父目录 `pyvenv.cfg` 改名备份为 `D:\anaconda3\envs\pyvenv.cfg.bak-codex-20260513`。
- 已验证 `ctrip` 环境恢复：`sys.prefix == D:\anaconda3\envs\ctrip`，`unicodedata` 可导入，`python -m pip --version` 成功。
- 已安装项目依赖并修复 `selenium-wire` 对 `pkg_resources` 的依赖问题。
- 已验证 Edge WebDriver 可启动。
- 已将采集配置限定为上海 -> 香港，2026-09-25 至 2026-10-07。
- 已加入程序结束后统一发送结果 CSV 附件的邮件逻辑。
- 已按 lyx 要求降低页面失败刷新频率。
- 已修复 SeleniumWire 与 pyOpenSSL/cryptography 版本不兼容问题；SeleniumWire 单次访问携程首页成功。

# 下一步动作
- 实际运行爬虫直到获取票价，或停在必须人工处理的登录/验证码/网站限制点。

# 阻塞项
- 普通沙箱内执行 conda 仍可能受权限限制，环境修复/依赖安装需在已授权的提升权限命令中进行。
- 日期年份待 lyx 确认；如无异议，按当前日期后的最近区间理解为 2026-09-25 至 2026-10-07。
- 真实爬虫运行可能触发携程登录、验证码、浏览器驱动版本匹配、网络访问限制；遇到账号/验证码/驱动选择等需要 lyx 决策的点会暂停确认。
