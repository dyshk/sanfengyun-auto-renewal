# 三丰云免费产品自动延期脚本

> ⚠️ **写在最前——关于三丰云的审核机制**
>
> 三丰云就是个恶心的 b 玩意，浪费我十几个小时编写自动化脚本，等实现自动提交后才发现：
> **审核只在工作时间进行，大约 3 小时内审完**。意思是——不上班不审核。
> 如果刚好你服务器过期赶上非工作时间，那不好意思，**自动删除你的实例，数据全没**。
>
> 所以这个脚本的意义在于：在到期前尽早提交延期，确保审核在工作时间内完成，避免实例被删。
> 但如果你到期时间恰好卡在周末或节假日——自求多福。

---

## 它能干嘛？

> 自动扫描 → 博客园发评测文章 → 三丰云填表单提交延期 → 钉钉通知，全程无人值守。

三丰云的免费云服务器（+5天/次）和免费虚拟主机（+30天/次）需要定期发评测文章提交延期。这个脚本帮你把整套流程全自动跑完：

| 步骤 | 做什么 | 怎么判断 |
|------|--------|---------|
| ① 扫描 | 访问三丰云控制面板，从 **DOM 页面文字** 提取到期时间 + 表单状态 | `form_status` 四态：`ready`（有发帖表单可提交）/ `in_review`（审核中，等结果）/ `not_yet`（未到时间，跳过）/ `not_activated`（未开通，跳过） |
| ② 发帖 | 博客园（cnblogs.com）自动生成评测文章并发布 | **只有 `form_status=ready` 才发帖**；模板随机拼接 + 当前时间占位符 |
| ③ 提交 | 三丰云后台填入博文 URL + 上传博文截图，提交延期表单 | 单张 JPG/PNG 截图（full_page）；提交成功 → 冷却 4h 等审核；审核中 → 2h 后再扫 |
| ④ 通知 | 每个阶段都推一条钉钉 Markdown 消息 | 加签模式安全，消息带"下次脚本执行时间" |

**两个实例各自独立倒计时**，哪个先到时间就先触发哪个，互不干扰。

---

## 目录结构

```
sanfengyun-auto-renewal/
├── README.md                 📖 本文件（给人看）
├── AI_SPEC.yaml              🤖 机器可读规约（给 AI 看，YAML 结构化，含可复用组件标注）
├── sanfengyun_renewal.py     ⭐ 主入口（命令行 / 持续运行模式）
├── scanner.py                登录三丰云 + DOM 扫描到期时间 / 延期状态
├── publisher.py              登录博客园 + 自动发文 + 页面截图
├── renewer.py                三丰云后台填写延期表单 + 提交
├── article_generator.py      文章生成器（模板随机拼接 + 时间占位符）
├── dingtalk_notify.py        钉钉机器人通知（加签，Markdown 格式）
├── config.yaml               🔧 配置文件（账号密码 / 产品列表 / 运行参数）
├── requirements.txt          Python 依赖
├── instance_timestamps.json  ⚡ 运行时生成：每个实例的下次触发时间戳
└── screenshots/              运行时生成：博文截图、扫描截图（自动创建）
```

### 各文件一句话说明

| 文件 | 作用 | 要不要改 |
|------|------|---------|
| [sanfengyun_renewal.py](sanfengyun_renewal.py) | **主入口**，三种运行模式（`--test` / `--once` / 持续循环）。run_loop 里有独立倒计时持久化逻辑，**核心常量在文件顶部**（STATE_FILE / SLEEP_SLICE / TRIGGER_DELAY） | 一般不用改 |
| [scanner.py](scanner.py) | DOM 页面元素抓取。`ensure_login()` 做登录检测，`scan_product()` 返回 `can_renew / expire_time / renew_time / form_status`（ready/in_review/not_yet/not_activated） | 一般不用改 |
| [publisher.py](publisher.py) | 博客园自动发文。`login()` + `publish()`；发布后跳转**公开页** full_page 截图，Pillow 压缩到 500KB 内 JPG | 一般不用改 |
| [renewer.py](renewer.py) | 三丰云填表单。`fill_and_submit()` 里 `dry_run=True` 只填不提交 | 一般不用改 |
| [article_generator.py](article_generator.py) | 文章模板池。想换话题/风格就改 `TITLE_TEMPLATES` / `INTRO_TEMPLATES` 这些列表 | **可以改，加自己的模板** |
| [dingtalk_notify.py](dingtalk_notify.py) | 钉钉通知格式。想改通知样式在这里调 Markdown | 一般不用改 |
| [config.yaml](config.yaml) | **所有账号、产品 URL、运行参数都在这里** | **必须改**（见下文配置详解） |
| [requirements.txt](requirements.txt) | Python 依赖列表 | 一般不用改 |
| `instance_timestamps.json` | **脚本自动生成**，保存每个实例下次触发的 Unix 时间戳。删了也没事，下次启动会自动重新扫 | 不用手动改 |
| `screenshots/` | **脚本自动生成**，存放所有截图：①扫描页面截图（排错用）②博客园文章公开页长截图（**提交给三丰云审核用，必须有**）③三丰云填表截图。目录不存在会自动 `mkdir`，不用手动建，也别提交到 git | 不用手动改 |

---

## 运行时自动生成的文件（不用手动建）

脚本第一次运行时会自动创建以下文件/目录，**不需要你手动建**，也**不要提交到 GitHub**：

| 文件/目录 | 什么时候生成 | 能不能删 | 删了会怎样 |
|----------|------------|---------|-----------|
| `screenshots/` | 脚本启动时 `mkdir(exist_ok=True)` | 可以删 | 下次运行自动重建；里面的截图会丢失（三丰云提交时需要重新生成） |
| `instance_timestamps.json` | 首次扫描完成后写入 | 可以删 | 下次启动会重新登录三丰云全量扫描重建（多花一次扫描时间） |
| `__pycache__/` | Python 导入模块时生成 | 可以删 | 自动重建 |
| `run.log`（如果你在 config.yaml 配了日志文件路径） | 脚本运行写日志时生成 | 可以删 | 删了重新生成，历史日志丢失 |

> 💡 **关于 screenshots 文件夹**：它是有用的，**别删**。脚本里 `publisher.py` 生成的博文公开页长截图会上传到三丰云作为延期凭证，`scanner.py` 和 `renewer.py` 的截图用于排错。目录不存在时脚本会自动创建。

---

## 前提版本

| 组件 | 最低版本 | 推荐版本 | 说明 |
|------|---------|---------|------|
| Python | **3.9** | 3.10 / 3.11 / 3.12 | 用到了类型注解和 strftime 的 `/` 替换 |
| Playwright | 1.40 | 最新 | 浏览器自动化引擎 |
| Pillow | 9.0 | 最新 | 截图压缩到 500KB 内（三丰云审核偏好小图） |
| 系统 | Ubuntu 20.04 / Debian 11 / CentOS 7+ | Ubuntu 22.04 | 需要有 root 或 sudo 权限安装 chromium 依赖 |
| 中文字体 | - | fonts-noto-cjk + fonts-wqy-zenhei | **Linux 服务器必须装！否则截图中文全是 □□□ 乱码** |
| 磁盘 | - | ≥ 1GB | Playwright chromium + 截图会占空间 |

---

## 快速上手（本地）

### 第 1 步：克隆 & 安装依赖

```bash
git clone https://github.com/你的用户名/sanfengyun-auto-renewal.git
cd sanfengyun-auto-renewal

# 装 Python 依赖
pip install -r requirements.txt

# 装 Playwright 浏览器（第一次会下载 chromium，几十 MB）
playwright install chromium
playwright install-deps chromium   # 服务器上跑必须执行这条！安装系统库
```

### 第 2 步：改配置

打开 `config.yaml`，改这几块：

```yaml
sanfengyun:
  phone: "你的三丰云手机号"     # ← 改
  password: "你的三丰云密码"     # ← 改

cnblogs:
  email: "你的博客园邮箱"        # ← 改
  password: "你的博客园密码"     # ← 改
  username: "你的博客园用户名"   # ← https://www.cnblogs.com/xxx 里的 xxx

dingtalk:
  enabled: true
  webhook: "https://oapi.dingtalk.com/robot/send?access_token=xxx"   # ← 改
  secret: "SECxxx"   # ← 改（机器人安全设置里复制）

products:
  - key: "vps"
    url: "https://www.sanfengyun.com/control/#/freeServer/你的实例ID"    # ← 改
  - key: "vhost"
    url: "https://www.sanfengyun.com/control/#/freeVhost/你的实例ID"     # ← 改
```

> 💡 不想用钉钉通知？把 `enabled: true` 改成 `false` 就行。

### 第 3 步：跑测试模式（只填表单，不真提交）

```bash
python3 sanfengyun_renewal.py --test
```

看到日志走完三个阶段（扫描 → 发文 → 填表），没有报错，**钉钉也收到了三条通知**，就说明环境 OK。

### 第 4 步：跑持续模式（自动倒计时，到点自动触发）

```bash
python3 sanfengyun_renewal.py
```

按 `Ctrl + C` 可以优雅退出。

---

## 首次运行会发生什么？

第一次跑 `--test` 或持续模式时，脚本会按顺序做这些事：

```
1. 读 config.yaml → 初始化日志、钉钉通知
2. 启动 chromium（headless=False + Xvfb 虚拟显示，绕过阿里云验证码检测）
3. 登录三丰云（清空旧 cookie → 填账号密码 → 修复 cookie domain → 验证）
4. 扫描所有产品（跳转到每个产品详情页 → 等 Vue 渲染 → 提取到期时间/表单状态）
   → 自动创建 instance_timestamps.json（记录每个产品下次触发时间）
   → 自动创建 screenshots/ 目录，保存扫描截图
5. 如果有产品 form_status=ready（可延期）：
   → 登录博客园（隐藏 webdriver 特征 + 模拟人类鼠标轨迹通过阿里云 checkbox 验证码）
   → 生成随机文章 → 发布 → 截文章公开页长图
   → 回到三丰云填 URL + 上传截图 → 提交（--test 模式只填不提交）
6. 每个阶段推一条钉钉通知
```

**常见现象（正常，不用慌）：**
- 扫描时页面会"卡住"5 秒 → 这是在等 Vue SPA 渲染到期时间，正常
- 博客园登录会弹阿里云 checkbox 验证码 → 脚本用 smoothstep 贝塞尔曲线模拟人类鼠标轨迹自动点击（最多重试 15 次）
- 持续模式等待时不开浏览器 → 只读 JSON 判断倒计时，到点才启动浏览器（节省资源）
- `--test` 模式最后三丰云表单只填不提交 → 这是设计如此，怕你误提交
- 第一次跑会慢一点（要全量扫描），之后读 json 跳过初始化扫描就快了

---

## 三种运行模式

| 命令 | 做什么 | 什么时候用 |
|------|--------|-----------|
| `python3 sanfengyun_renewal.py --test` | 扫描 → 发文 → **填表不提交**（dry_run=True） | 第一次跑、改了配置后验证 |
| `python3 sanfengyun_renewal.py --once` | 扫描 → **可以延期的都完整提交一次** | 临时手动触发一次 |
| `python3 sanfengyun_renewal.py` | 启动持续循环，每实例独立倒计时，到点自动执行 | 服务器上 7×24 挂着跑 |

---

## 配置文件详解（config.yaml）

### 🔧 必须改的字段

| 位置 | 字段 | 说明 |
|------|------|------|
| `sanfengyun.phone` | 手机号 | 你注册三丰云用的手机号 |
| `sanfengyun.password` | 密码 | 三丰云登录密码 |
| `cnblogs.email` | 邮箱 | 博客园登录邮箱 |
| `cnblogs.password` | 密码 | 博客园登录密码 |
| `cnblogs.username` | 用户名 | 博客园地址 `https://www.cnblogs.com/xxx` 里的 `xxx` |
| `dingtalk.webhook` | Webhook | 钉钉群 → 设置 → 智能群助手 → 添加机器人（自定义） → 复制 URL |
| `dingtalk.secret` | 加签密钥 | 机器人安全设置 → 加签 → 复制 `SEC` 开头那串 |
| `products[*].url` | 实例 URL | 三丰云控制面板里点进实例详情页，复制浏览器地址栏 |

### ✏️ 可选调整的字段

| 位置 | 默认值 | 说明 |
|------|--------|------|
| `settings.dry_run` | `false` | `true`=只填表单不提交（测试用）；`false`=真的提交延期 |
| `settings.sanitize_keywords` | `["三丰云", "三丰"]` | 博客园会拦截"三丰云"这三个字，发布后自动替换 |
| `logging.file` | `""` | 留空只输出控制台；填路径（如 `run.log`）则同时写日志文件 |
| `products[*].enabled` | `true` | `false`=跳过这个产品（比如你只有 vps，把 vhost 设 false） |
| `settings.scan_scope` | `"all"` | 扫描范围：`all`=两个都扫；`vps`=只扫云服务器；`vhost`=只扫虚拟主机。钉钉通知也只包含被扫描的产品 |

### 🔒 不用改的字段

`login_url`、`ptype`、`level` 这些保持默认就行。

> ⚠️ `check_interval`、`early_submit_seconds` 是**遗留字段**，当前版本代码未使用（倒计时由 `instance_timestamps.json` 独立管理），保留仅为兼容旧配置，可忽略。

---

## 部署到服务器（Ubuntu / Debian）

### 第 1 步：安装系统依赖

```bash
sudo apt update
sudo apt install -y python3 python3-pip python3-venv

# Playwright 需要的系统库（必须，否则 chromium 启动报缺库）
sudo apt install -y libnss3 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libatspi2.0-0 libx11-xcb1

# ⚠️ 中文字体（必须！否则截图里中文全是 □□□ 乱码）
sudo apt install -y fonts-noto-cjk fonts-wqy-zenhei fonts-wqy-microhei
fc-cache -fv

# ⚠️ Xvfb 虚拟显示（必须！博客园阿里云验证码会检测 headless 模式）
sudo apt install -y xvfb
```

### 第 2 步：创建目录 + 上传代码

```bash
sudo mkdir -p /root/sanfengyun
sudo chown -R $USER:$USER /root/sanfengyun

# 方式 A：git clone
cd /root/sanfengyun
git clone https://github.com/你的用户名/sanfengyun-auto-renewal.git .

# 方式 B：本机打包 scp 过去
# 在本机：tar czf sanfengyun.tar.gz sanfengyun-auto-renewal/
# 在服务器：scp user@你的服务器IP:~/sanfengyun.tar.gz /root/
#          tar xzf /root/sanfengyun.tar.gz -C /root/sanfengyun --strip-components=1
```

### 第 3 步：安装 Python 依赖

```bash
cd /root/sanfengyun
pip3 install -r requirements.txt --break-system-packages   # Ubuntu 24.04+ 用这个
# 或用 venv（推荐）：
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

# 安装 chromium
playwright install chromium
playwright install-deps chromium
```

### 第 4 步：修改 config.yaml（服务器版本）

```bash
vi /root/sanfengyun/config.yaml
```

重点检查：

```yaml
settings:
  dry_run: false          # ← 部署后改成 false，真的提交延期

logging:
  file: "/root/sanfengyun/run.log"   # ← 服务器上建议写日志文件，方便排错
```

### 第 5 步：先跑一次测试

```bash
cd /root/sanfengyun
source .venv/bin/activate    # 如果用 venv

python3 sanfengyun_renewal.py --test
```

走完三个阶段、钉钉收到通知 → 环境 OK。

### 第 6 步：用 systemd 守护（7×24 自动重启）

创建服务文件：

```bash
sudo vi /etc/systemd/system/sanfengyun.service
```

内容：

```ini
[Unit]
Description=三丰云自动延期脚本
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=/root/sanfengyun
ExecStart=/root/sanfengyun/.venv/bin/python3 /root/sanfengyun/sanfengyun_renewal.py
Restart=on-failure
RestartSec=30
# 如果没用 venv，把上面两个路径换成系统的 python3 就行
# ExecStart=/usr/bin/python3 /root/sanfengyun/sanfengyun_renewal.py

[Install]
WantedBy=multi-user.target
```

启动 & 设置开机自启：

```bash
sudo systemctl daemon-reload
sudo systemctl start sanfengyun
sudo systemctl enable sanfengyun

# 查看实时日志
journalctl -u sanfengyun -f

# 查看进程状态
systemctl status sanfengyun
```

### 常用运维命令

```bash
systemctl restart sanfengyun     # 重启（改了 config.yaml 后必须重启才生效）
systemctl stop sanfengyun        # 停止
tail -f /root/sanfengyun/run.log # 直接看脚本日志文件
```

---

## 倒计时持久化机制

### 核心思路

两个实例 **各自独立保存** 下次允许提交的 Unix 时间戳到 `instance_timestamps.json`：

```json
{
  "freeServer_532542": {"next_allow_submit_ts": 1788717483},
  "freeVhost_6631220": {"next_allow_submit_ts": 1789634902}
}
```

### 触发条件

```
当前时间 >= next_allow_submit_ts + 60
                                  ↑
                          TRIGGER_DELAY = 60s
                          缓冲一下三丰云和本地的时间差
```

### 运行流程

```
脚本启动
  │
  └─ 读 instance_timestamps.json
     ├─ 有缺失实例？→ 登录三丰云 DOM 扫描补全，写回 json
     └─ json 完整 → 跳过初始化扫描（节省时间和请求）

主循环（每 60s 醒一次）
  │
  ├─ 遍历实例，计算 remain = next_ts + 60 - now
  │   ├─ remain <= 0      → 到点了，加入 need_trigger_keys
  │   ├─ remain <= 3600   → 钉钉推"即将触发"紧急提醒（每实例只推一次）
  │   └─ remain > 3600    → 打印进度日志：[等待中] 免费云服务器 → 09-06 07:59
  │
  ├─ 有实例到点 → 执行完整流程（_execute_single_product）
  │   │
  │   ├─ Phase A: DOM 扫描 → 得到 form_status
  │   │
  │   ├─ form_status = ready（有发帖表单）
  │   │   → 博客园发文 → 三丰云填表提交
  │   │   → next_ts = now + 4h（等审核结果）
  │   │
  │   ├─ form_status = in_review（审核中）
  │   │   → 不发帖、不提交
  │   │   → next_ts = now + 2h（2h 后再扫，看审核过了没）
  │   │   → 循环扫描：若仍审核中，继续 2h 后再扫；
  │   │     若变成 not_yet，取页面"请在XX后提交"时间；
  │   │     若变成 ready，执行发文+提交
  │   │
  │   └─ form_status = not_yet（未到时间）
  │       → 不发帖、不提交
  │       → next_ts = 页面上的"请在 XX 后提交"时间
  │
  └─ sleep 60s → 下一轮
```

### 钉钉通知机制

脚本在以下时机发送钉钉通知：

| 时机 | 通知内容 |
|------|---------|
| 脚本启动 | 启动时间、监控产品数、持久化文件路径 |
| 到点前 30min | "即将触发"提醒（每实例每轮只推一次，触发后清除标记） |
| 触发执行 | "🚀 倒计时已触发"，开始扫描三丰云页面状态 |
| 扫描结果 | DOM 扫描后推送 form_status、到期时间、可提交时间 |
| ready → 提交成功 | 博文 URL、提交结果、下次扫描时间（4h 后） |
| ready → 提交失败 | 失败原因、下次重试时间（30min） |
| in_review | "审核中，脚本将在 XX 时间再次扫描"（2h 后） |
| not_yet | "未到可提交时间，下次扫描 XX" |
| not_activated | "产品未开通，24h 后再检查" |
| 脚本异常 | 异常错误信息 |

**通知时序示例**：
1. 倒计时 ≤ 30 分钟 → 推送"即将触发"提醒（仅 1 次）
2. 到点 → 推送"已触发"通知 → 扫描 DOM
3. 扫描完 → 推送"扫描结果"（form_status 详情）
4. 根据状态 → 推送"审核中"/"提交成功"/"未到时间"等结果

**为什么每次扫描后都通知下次启动时间？**
每次触发执行后，脚本会根据 `form_status` 计算下次扫描时间并写入 `instance_timestamps.json`，同时通过 `notify_waiting` 通知用户。这样用户能清楚知道脚本何时会再次运行，无需手动查看日志。审核中状态每 2h 扫描一次，未到时间状态则等到页面指定的时间点。

### 持续模式主循环优化

主循环每 60 秒检查一次，但**只在需要触发或初始化时才启动浏览器**：

1. 先读 `instance_timestamps.json`（不启动浏览器）
2. 判断是否有实例到达触发时间，或 JSON 缺失实例
3. 如果都不需要 → 只打一行日志 `[等待中]`，sleep 60s 继续
4. 如果有触发或需要初始化 → 启动浏览器，执行扫描/触发流程

这样避免了每 60 秒启动一次浏览器的资源浪费。

### 登录与反检测机制

博客园使用阿里云 captcha checkbox 验证码，headless 模式会被检测为机器人。脚本采用以下策略绕过检测：

| 策略 | 作用 |
|------|------|
| **Xvfb 虚拟显示** | 在无显示器的服务器上提供虚拟 X11 显示，让 `headless=False` 模式可以运行 |
| **headless=False** | 非无头模式不会被阿里云验证码检测为自动化工具 |
| **隐藏 webdriver 特征** | `add_init_script` 覆盖 `navigator.webdriver`、`window.chrome`、`plugins`、`languages` |
| **playwright-stealth** | 注入 stealth 脚本，进一步隐藏自动化痕迹 |
| **smoothstep 贝塞尔曲线** | 鼠标移动用 `t² × (3-2t)` 缓动函数，10-20 步曲线移动到目标，模拟人类轨迹 |
| **随机停顿** | 点击前 100-300ms 停顿，点击后 5s 等待验证结果 |
| **15 次重试** | 验证失败自动重试，每次轨迹不同 |

三丰云登录不涉及验证码，使用简单的表单登录 + cookie domain 修复。

### 关键设计：先查入口再发帖

> **绝对不会先发帖再去检查能不能提交**。每次触发都先 DOM 扫描 `form_status`，只有 `ready` 才去博客园发文。如果三丰云页面显示"审核中"或"未到时间"，直接跳过，避免生成无效文章被博客园判定灌水。

### 为什么要持久化？

| 情况 | 没持久化 | 有持久化 |
|------|---------|---------|
| 脚本进程崩了重启 | 立刻重新全量扫描（浪费 API） | 读 json，直接恢复倒计时 |
| 服务器重启 | 同上 | 同上 |
| 两个实例一个到点一个没到 | 全量扫描 + 统一 sleep | 各自独立，只跑那个到点的 |

### 关键原则（方案2 原文）

> **本地 json 只是倒计时记录，一切业务判断以三丰云 DOM 页面为准**。即使 json 存的时间戳乱了，每次触发都会重新访问页面，不会乱发帖乱提交。

---

## 常见问题 FAQ

### Q1：脚本跑起来但钉钉没收到通知？

检查：
1. `config.yaml` 里 `dingtalk.enabled` 是否为 `true`
2. 机器人 Webhook 里的 `access_token` 和 `secret` 是否复制完整
3. 钉钉群 → 机器人安全设置 → 加签密钥（`SEC` 开头）有没有对上
4. 服务器能不能访问 `oapi.dingtalk.com`（`curl -I https://oapi.dingtalk.com/robot/send`）

### Q2：博客园发布时说"提交内容中含有不允许的词"？

默认配置里 `sanitize_keywords` 是 `["三丰云", "三丰"]`，发布后文章里会自动替换。如果替换后的词还是被拦，改成别的：

```yaml
sanitize_keywords:
  - "三丰云"
  - "SFY"     # 换成你想替换成什么
```

### Q3：服务器上跑 Chromium 报 "error while loading shared libraries: libnss3.so"？

Playwright 没装系统依赖。执行：

```bash
playwright install-deps chromium
```

### Q3.5：三丰云收到的截图里中文全是 □□□ 方块？

**服务器没装中文字体**，Chromium 渲染中文时全部变成豆腐块。执行：

```bash
sudo apt install -y fonts-noto-cjk fonts-wqy-zenhei fonts-wqy-microhei
fc-cache -fv
# 装完重启脚本即可，不用重装 chromium
```

本地 macOS / Windows 一般自带中文字体，不会有这个问题。

### Q4：脚本进程崩了会自动重启吗？

如果按 systemd 方式部署的（推荐），会。`Restart=on-failure` 配置会让它异常退出后 30s 自动拉起。

### Q5：我只有一个产品（比如只有 vps 没有 vhost）？

```yaml
products:
  - key: "vps"
    name: "免费云服务器"
    enabled: true
    url: "https://www.sanfengyun.com/control/#/freeServer/你的实例ID"
  # 把 vhost 那段整个删掉，或者留着 enabled: false
```

### Q6：我想换一个博客平台（CSDN、知乎）？

改 `publisher.py`，换成你要的平台的登录 + 发文逻辑。接口都在 `publisher.py` 的 `login()` / `publish()` 里，主入口不动。

### Q7：想自己改文章模板？

打开 `article_generator.py`，顶部有 `TITLE_TEMPLATES` / `INTRO_TEMPLATES` / `CONFIG_PARAGRAPHS` 等列表。你想换风格就往里面加自己的文案。

带时间占位符的模板用 `{NOW_FULL}`（`2026年09月05日22:20`）或 `{NOW_DATE}`（`2026年09月05日`），运行时自动替换。

### Q8：`--test` 和 `--once` 有啥区别？

- `--test`：所有 **执行** 步骤都走，但三丰云表单只填不提交（`dry_run=True` 硬编码）
- `--once`：真的提交。`config.yaml` 里的 `dry_run` 决定要不要真提交。

### Q9：instance_timestamps.json 能手动改吗？

可以，但没必要。脚本启动时会用 DOM 扫描结果覆盖它。删了也没事，下次启动会自动重建。

---

## 安全提醒

### ⚠️ config.yaml 包含真实账号密码

`config.yaml` 里有三丰云/博客园账号密码和钉钉密钥。**推到 GitHub 前必须脱敏**，否则账号会泄露、机器人会被滥用。

#### 方法一：手动改占位符（最简单）

上传前把 `config.yaml` 里的真实值改成 `你的xxx`：

```yaml
sanfengyun:
  phone: "你的三丰云手机号"
  password: "你的三丰云密码"
cnblogs:
  email: "你的博客园邮箱"
  password: "你的博客园密码"
  username: "你的博客园用户名"
dingtalk:
  webhook: "https://oapi.dingtalk.com/robot/send?access_token=你的token"
  secret: "SEC你的加签密钥"
```

#### 方法二：用 .gitignore 排除（推荐，不会误传）

在项目根目录创建 `.gitignore`：

```gitignore
# 配置文件（含账号密码，绝不上传）
config.yaml

# 运行时生成的文件
screenshots/
instance_timestamps.json
run.log
*.log

# Python
__pycache__/
*.pyc
.venv/
venv/

# IDE
.idea/
.vscode/
```

然后额外复制一份 `config.yaml` 为 `config.example.yaml`（填占位符），提交到 git 供新人参考：

```bash
cp config.yaml config.example.yaml
# 手动把 config.example.yaml 里的真实值改成占位符
git add config.example.yaml README.md AI_SPEC.yaml *.py requirements.txt
git commit -m "init"
```

新人 clone 后：`cp config.example.yaml config.yaml`，再填自己的账号。

### 🔑 钉钉机器人安全

- 机器人安全设置**必须选"加签"**，不要用"自定义关键词"或"IP 段"（加签最安全）
- `secret`（`SEC` 开头那串）和 `webhook` 里的 `access_token` 都要保管好
- 不要在公开仓库、issue、截图里暴露钉钉密钥
