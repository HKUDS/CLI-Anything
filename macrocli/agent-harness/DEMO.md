# MacroCLI Demo — gedit 完整测试方案

本文档记录 MacroCLI 在 **Linux 无头服务器 + Xvfb + noVNC** 环境下的完整测试过程，
包括虚拟桌面搭建、VNC 远程查看、宏执行和录制回放的全链路验证。

---

## 环境架构

```
本地浏览器
    │  SSH 隧道 (16080 → 16080)
    ▼
远程 Linux 服务器
    │
    ├─ Xvfb :99         虚拟显示器 1920x1080
    ├─ openbox          窗口管理器
    ├─ x11vnc           VNC 服务 (只监听 localhost:5900)
    ├─ websockify       WebSocket → VNC 代理 (16080)
    └─ gedit            被操控的 GUI 应用
```

---

## 第一步：安装依赖

```bash
# 虚拟显示器和 VNC
sudo apt install xvfb x11vnc openbox xdotool wmctrl

# GUI 应用（demo 目标）
sudo apt install gedit

# noVNC（浏览器查看桌面）
sudo apt install novnc websockify

# AT-SPI 语义控制（可选，GTK 应用）
sudo apt install python3-pyatspi

# MacroCLI Python 依赖
conda activate macrocli   # 或你的环境名
pip install -e "path/to/macrocli/agent-harness[visual]"
# 等价于: pip install mss Pillow numpy pynput
```

---

## 第二步：启动虚拟桌面

```bash
# 1. 启动 Xvfb 虚拟显示器（:99 号，1920x1080 24位色）
Xvfb :99 -screen 0 1920x1080x24 -ac &

# 2. 设置 DISPLAY（后续所有命令都需要）
export DISPLAY=:99

# 3. 启动窗口管理器（让窗口能正常显示和拖动）
openbox &

# 4. 设置桌面背景色（避免纯黑）
xsetroot -solid gray

# 5. 启动 VNC 服务，只监听本地，允许多连接
x11vnc -display :99 -nopw -listen localhost -rfbport 5900 \
    -forever -shared -bg -o /tmp/x11vnc.log

# 6. 启动 noVNC websocket 代理
websockify --web /usr/share/novnc 16080 localhost:5900 &

# 验证服务启动
ss -tlnp | grep -E "5900|16080"
```

期望输出：
```
LISTEN  127.0.0.1:5900   ← x11vnc
LISTEN  0.0.0.0:16080    ← websockify
```

---

## 第三步：连接 VNC 查看桌面

在**本地机器**开 SSH 隧道：

```bash
ssh -L 16080:localhost:16080 user@your-server -N
```

然后浏览器访问：

```
http://localhost:16080/vnc.html
```

点击 **Connect**，无需密码，即可看到虚拟桌面。

> **注意：** 如果 Connect 后显示"连接已中断"，通常是 x11vnc 的客户端连接数超限。
> 重启 x11vnc 并加 `-shared` 参数即可：
> ```bash
> pkill x11vnc
> x11vnc -display :99 -nopw -listen localhost -rfbport 5900 -forever -shared -bg
> ```

---

## 第四步：检查后端可用性

```bash
export DISPLAY=:99
conda activate macrocli
cd path/to/macrocli/agent-harness

cli-anything-macrocli --json backends
```

期望输出（所有后端 available: true）：

```json
{
  "native_api":    { "available": true,  "priority": 100 },
  "gui_macro":     { "available": true,  "priority": 80  },
  "visual_anchor": { "available": true,  "priority": 75  },
  "file_transform":{ "available": true,  "priority": 70  },
  "semantic_ui":   { "available": true,  "priority": 50  },
  "recovery":      { "available": true,  "priority": 10  }
}
```

---

## Demo A：手写宏执行

### A1. 打开 gedit

```bash
cli-anything-macrocli --json macro run gedit_new_window
```

VNC 里能看到 gedit 窗口弹出。

输出示例：
```json
{
  "success": true,
  "telemetry": { "duration_ms": 39, "backends_used": ["native_api", "semantic_ui"] }
}
```

> **实现细节：** `gedit_new_window` 用 `native_api` 的 `start_process` action 后台
> 启动 gedit（不等待进程退出），然后 `semantic_ui` 的 `wait_for_window` 等待窗口出现。

### A2. 输入文字并保存

```bash
cli-anything-macrocli --json macro run gedit_type_and_save \
    --param "text=Hello from MacroCLI!"
```

VNC 里能看到文字逐字输入到 gedit，然后触发 Ctrl+S。

输出示例：
```json
{
  "success": true,
  "steps": [
    { "backend_used": "semantic_ui",   "output": {"focused": "gedit", "method": "wmctrl"} },
    { "backend_used": "visual_anchor", "output": {"typed": 20} },
    { "backend_used": "visual_anchor", "output": {"hotkey": "ctrl+s"} }
  ],
  "telemetry": { "duration_ms": 774 }
}
```

> **实现细节：** 三个后端串联——`semantic_ui` 用 wmctrl 聚焦窗口，`visual_anchor`
> 用 pynput 注入键盘事件，`visual_anchor` 发送 Ctrl+S 快捷键。

### A3. 另存为指定路径

```bash
cli-anything-macrocli --json macro run gedit_save_as \
    --param output_path=/tmp/macrocli_demo.txt
```

执行过程（可在 VNC 观察）：
1. Ctrl+Shift+S 弹出 Save As 对话框
2. Ctrl+L 打开路径输入框
3. Ctrl+A 清空已有内容
4. 输入 `/tmp/macrocli_demo.txt`
5. Enter 确认

```bash
# 验证文件已创建
cat /tmp/macrocli_demo.txt
```

---

## Demo B：录制宏（核心功能）

录制功能把一次手工操作自动转成可重复调用的宏。

### 录制原理

```
用户操作 GUI
    │
pynput 监听鼠标键盘事件
    │
每次点击：
  xdotool getwindowfocus → 获取焦点窗口名称和位置
  计算点击在窗口内的百分比坐标 (x_pct, y_pct)
  → 生成 click_relative 步骤（窗口锚点，不依赖绝对坐标）
    │
键盘输入：
  累积字符（含空格）→ 生成 type_text 步骤
  快捷键组合 → 生成 hotkey 步骤
    │
Ctrl+Alt+S 停止录制
    │
自动写出 YAML 宏文件
```

**为什么用窗口锚点而不是绝对坐标：**
点击空白文本区会截到全白图片，模板匹配无法识别。改用窗口相对坐标
（`click_relative`），回放时先找到窗口位置，再按百分比算出实际坐标，
窗口移动到任何地方都能正确点击。

### 录制操作

```bash
# 开始录制，命名为 my_workflow
cli-anything-macrocli macro record my_workflow \
    --output-dir /tmp/my_recording \
    --timeout 30    # 30秒后自动停止，或手动 Ctrl+Alt+S
```

终端显示：
```
Recording 'my_workflow'. Press Ctrl+Alt+S to stop.
[recorder] Recording 'my_workflow'. Press Ctrl+Alt+S to stop.
```

**现在操作 gedit（录制器会捕获这些动作）：**
1. 在 VNC 里点击 gedit 文本区
2. 输入一段文字
3. 按 Ctrl+S 保存

按 Ctrl+Alt+S 停止（或等待超时），自动生成：

```
/tmp/my_recording/
├── my_workflow.yaml              ← 宏定义文件
└── my_workflow_templates/        ← 有特征区域的截图模板
    └── step_001_click.png        ← 若点击区域有特征才会保存
```

生成的 YAML 示例：

```yaml
name: my_workflow
steps:
  - id: step_001_click
    backend: visual_anchor
    action: click_relative         # 窗口锚点，不是绝对坐标
    params:
      window_title: gedit          # 从 xdotool getwindowfocus 获取
      x_pct: 0.35                  # 点击位置在窗口宽度的 35%
      y_pct: 0.33                  # 点击位置在窗口高度的 33%

  - id: step_002_type
    backend: visual_anchor
    action: type_text
    params:
      text: hello world            # 空格正确合并（不再被切成 hotkey）

  - id: step_003_hotkey
    backend: visual_anchor
    action: hotkey
    params:
      keys: ctrl+s
```

### 回放录制的宏

```bash
# 先清空 gedit 内容
# 然后回放
cli-anything-macrocli --json macro run my_workflow \
    --macro-file /tmp/my_recording/my_workflow.yaml
```

实际测试输出：
```json
{
  "success": true,
  "telemetry": {
    "duration_ms": 486,
    "steps_run": 3,
    "backends_used": ["visual_anchor"]
  }
}
```

VNC 截图验证（`hello world` 出现在 gedit）：

```
gedit 窗口标题: macrocli_test_final.txt (/tmp) - gedit
内容: hello world
状态: 已保存（标题栏无 * 号）
```

---

## Demo C：transform_json（file_transform 后端）

> ⚠️ **未在本次测试中验证，仅供参考。**

不需要 GUI，直接操作 JSON 文件：

```bash
# 创建测试文件
echo '{"app": "draw.io", "version": 1}' > /tmp/config.json

# 用宏修改嵌套 key
cli-anything-macrocli --json macro run transform_json \
    --param file=/tmp/config.json \
    --param key=settings.theme \
    --param value=dark

# 验证
cat /tmp/config.json
# {"app": "draw.io", "version": 1, "settings": {"theme": "dark"}}
```

---

## 常见问题

**Q: `macro run gedit_new_window` 超时 30 秒**

原因：`run_command` 会等待进程退出，GUI 应用永远不会退出。
解决：改用 `start_process` action（本项目已修复）。

**Q: `wait_for_window` 找不到窗口**

原因：`conda run` 会清除 `DISPLAY` 环境变量。
解决：激活 conda 环境后直接运行，不要用 `conda run`：
```bash
conda activate macrocli
export DISPLAY=:99
cli-anything-macrocli ...
```

**Q: VNC Connect 后显示"连接已中断"**

原因：x11vnc 默认不允许多个客户端同时连接。
解决：重启 x11vnc 并加 `-shared`：
```bash
pkill x11vnc
x11vnc -display :99 -nopw -listen localhost -rfbport 5900 -forever -shared -bg
```

**Q: 录制回放时点击位置不准**

原因：窗口大小与录制时不同，百分比坐标偏移。
解决：确保回放时窗口大小与录制时一致，或调整宏里的 `x_pct`/`y_pct`。

**Q: 模板图全白，click_image 永远超时**

原因：点击了空白区域（如文本编辑区），截图无特征。
解决：录制器已自动检测低方差图片，改用 `click_relative` 替代。

---

## 验证结果汇总

| 宏 | 后端 | 结果 | 耗时 |
|----|------|------|------|
| `gedit_new_window` | native_api + semantic_ui | ✓ | ~40ms |
| `gedit_type_and_save` | semantic_ui + visual_anchor | ✓ | ~774ms |
| `gedit_save_as` | semantic_ui + visual_anchor | ✓ | ~1847ms |
| `transform_json` | file_transform | ⚠️ 未验证 | — |
| `macro record` + 回放 | visual_anchor | ✓ | ~486ms |

---

## 对接其他应用

同样的流程适用于任何 Linux GUI 应用：

| 应用 | 推荐后端 | 说明 |
|------|----------|------|
| Inkscape | `native_api` (`--actions`) | 有完整命令行接口 |
| GIMP | `native_api` (Script-Fu) | 脚本接口强大 |
| LibreOffice | `native_api` (`--headless`) | UNO API |
| draw.io | `file_transform` + `visual_anchor` | XML 格式可直接编辑 |
| 任意 GUI 应用 | `macro record` + `visual_anchor` | 录制一次，窗口锚点回放 |
