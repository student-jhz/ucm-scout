# UCM-Scout 设计文档

## 1. 架构概览

```
┌─────────────────────────────────────────────────────────┐
│                     main.py (入口)                       │
└──────────────────────────┬──────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────┐
│              gui/main_window.py (Tk 主窗口)              │
│   ┌──────────────┐ ┌──────────────┐ ┌──────────────┐    │
│   │  SSH Panel   │ │ Scenario Par │ │  Language Sel│    │
│   └──────────────┘ └──────────────┘ └──────────────┘    │
│   ┌──────────────────────────────────────────────────┐   │
│   │              ttk.Notebook (3 tabs)               │   │
│   │  ┌──────────┐  ┌──────────┐  ┌──────────┐      │   │
│   │  │ Step 1   │  │ Step 2   │  │ Step 3   │      │   │
│   │  │ 带宽测试 │  │ TTFT测试 │  │ 收益分析 │      │   │
│   │  └────┬─────┘  └────┬─────┘  └────┬─────┘      │   │
│   └───────┼─────────────┼─────────────┼────────────┘   │
└───────────┼─────────────┼─────────────┼────────────────┘
            │             │             │
┌───────────▼──┐  ┌───────▼──┐  ┌──────▼────────────┐
│ core/ucm_    │  │ core/    │  │ core/analyzer.py  │
│ bandwidth.py │  │ ttft_    │  │                    │
│              │  │ test.py  │  │                    │
│ UcmBandwidth │  │ TTFTTest │  │ Analyzer           │
│ Controller   │  │ Controller│  │                    │
└──────┬───────┘  └─────┬────┘  └────────────────────┘
       │                │
       ▼                ▼
┌──────────────┐  ┌──────────────┐
│ core/ssh_    │  │  requests    │
│ client.py    │  │  (HTTP)      │
│              │  │              │
│ SSHClient    │  │              │
└──────┬───────┘  └──────────────┘
       │
       ▼  SSH paramiko
   [Remote Linux Host]
```

### 分层设计

| 层 | 目录 | 职责 |
|----|------|------|
| 入口 | `main.py` | 创建 MainWindow，启动 Tk 事件循环 |
| 表现层 | `gui/` | Tkinter UI 组件，每个 Tab 一个 Panel 类 |
| 业务层 | `core/` | 控制器类，编排业务逻辑，无 UI 依赖 |
| 基础设施 | `core/ssh_client.py`, `core/logger.py` | SSH 通信、日志 |
| 翻译 | `i18n.py` | 中英双语，运行时切换 |
| 远端脚本 | `remote_scripts/` | 上传到远端容器执行的独立脚本 |

---

## 2. 模块职责

### 2.1 `main.py`
入口脚本，创建 `MainWindow` 实例并进入 Tk 主循环。

### 2.2 `config.py`
全局路径和默认值常量。PyInstaller 打包后通过 `sys._MEIPASS` 定位资源。

### 2.3 `i18n.py`
- 中英双语翻译字典（189 个 key）
- `Translator` 类：`tr(key, **fmt)` 翻译 + 格式化
- `on_lang_change(fn)` 注册监听器，语言切换时自动通知各组件刷新

### 2.4 `core/ssh_client.py`
- `SSHClient`：基于 paramiko 的 SSH 封装
- `connect(timeout)`, `disconnect()`, `upload_file()`, `execute()`（支持 stdout/stderr 流式回调）
- `test_connection()`：连接后验证

### 2.5 `core/logger.py`
- `LogManager`：创建带时间戳的日志文件，统一日志接口

### 2.6 `core/ucm_bandwidth.py` — 带宽测试控制器
- 编排整个 Docker + UCM Store 带宽测试流程
- 核心方法：`run()` 包含 13 个子步骤，每步有 `[module] OK/FAIL` 日志

### 2.7 `core/ttft_test.py` — TTFT 测试控制器
- 在线模式：向 vLLM API 发送流式请求，测量首 token 延迟
- 分别测试 Cold（完全 prefill）和 Hot（HBM PC 命中）场景

### 2.8 `core/analyzer.py` — 收益分析器
- 接收带宽和 TTFT 数据，计算 UCM PC TTFT 范围、平均值、比值

### 2.9 `core/demo.py` — 本地演示模式
- `MockSSHClient`：模拟 SSH 命令返回，支持 docker images、docker run/exec/stop、config.json 解析等
- `MockVLLMServer`：本地 HTTP 服务，模拟 vLLM API（/health、/v1/models、/v1/completions）

### 2.10 `gui/widgets.py` — 可复用 UI 组件
- `ScrollableLogFrame`：暗色主题日志查看器，自动滚动
- `LabeledEntry`：标签 + 输入框组合，支持 `set_label()` 切换语言
- `SSHConnectionPanel`：SSH 连接面板，三种状态（disconnected/connecting/connected）
- `ScenarioParamsPanel`：请求长度 + 并发数
- `RemoteDirBrowser`：远端 Linux 目录浏览器（Toplevel 弹窗），通过 SSH `ls -1p` 列出内容

### 2.11 `gui/main_window.py` — 主窗口
- 组装所有 UI 组件
- 语言切换下拉框（en/zh）
- Demo Mode 复选框
- SSH 连接/断开逻辑（后台线程）
- 全局日志窗

### 2.12 `gui/step1_panel.py` — Step1 标签页
- 模型路径（远端目录浏览器）、Docker 镜像（自动刷新+输入筛选）、UCM 包/依赖（本地文件选择）、存储路径（远端目录浏览器）、TP 数量、输出目录
- 自动解析 config.json 显示 shard_size / shard_number
- 后台线程执行 UcmBandwidthController

### 2.13 `gui/step2_panel.py` — Step2 标签页
- 服务 URL、模型路径、模型名
- 后台线程执行 TTFTTestController
- 双结果展示：Full Prefill TTFT + HBM PC TTFT

### 2.14 `gui/step3_panel.py` — Step3 标签页
- 带宽/TTFT 手动输入 + "From Step1/Step2" 自动回填
- 调用 Analyzer 输出 UCM PC TTFT 范围、平均值、比值

### 2.15 `remote_scripts/ucm_bench.py` — 容器内执行
- 独立的 UCM Store 带宽测试脚本
- 通过 `multiprocessing` + `Barrier` 支持 TP 并行（worker_number）
- 调用 `UcmPipelineStore`（Posix + AIO）的 `dump_data` / `load_data`
- 输出 JSON 结果文件

---

## 3. 时序图

### 3.1 SSH 连接流程

```
用户           MainWindow        SSHConnectionPanel        后台线程           SSHClient        远端主机
 │                │                     │                     │                  │                │
 │  点击 Connect  │                     │                     │                  │                │
 │──────────────>│                     │                     │                  │                │
 │                │  get_values()      │                     │                  │                │
 │                │───────────────────>│                     │                  │                │
 │                │  host/user/pwd     │                     │                  │                │
 │                │<───────────────────│                     │                  │                │
 │                │                     │                     │                  │                │
 │                │  校验: host/user/pwd 为空 → messagebox     │                  │                │
 │                │                     │                     │                  │                │
 │                │  set_connecting()   │                     │                  │                │
 │                │───────────────────>│ Orange "connecting"  │                  │                │
 │                │                     │                     │                  │                │
 │                │ start _connect() 后台线程                   │                  │                │
 │                │─────────────────────────────────────────>│                  │                │
 │                │                     │                     │  [demo? MockSSH  │                │
 │                │                     │                     │   else SSHClient]│                │
 │                │                     │                     │  connect(10s)    │                │
 │                │                     │                     │─────────────────>│  TCP 握手       │
 │                │                     │                     │<─────────────────│                 │
 │                │                     │                     │  test_connection │                │
 │                │                     │                     │─────────────────>│  echo ok;uname  │
 │                │                     │                     │<─────────────────│                 │
 │                │                     │                     │                  │                │
 │                │ set_connected(True/False) via self.after()                    │                │
 │                │<─────────────────────────────────────────│                  │                │
 │                │  Green "connected" / Gray "disconnected" │                  │                │
 │                │───────────────────>│                     │                  │                │
 │                │                     │                     │                  │                │
 │  [SSH日志+全局日志]                   │                     │                  │                │
 │<──────────────│                     │                     │                  │                │
```

### 3.2 Step 1: UCM 带宽测试

```
用户      Step1Panel    后台线程    UcmBandwidth    SSHClient         远端主机(Docker)
 │           │            │         Controller         │                   │
 │  Execute  │            │             │              │                   │
 │──────────>│            │             │              │                   │
 │           │ 校验必填字段│             │              │                   │
 │           │ 存储路径确认│             │              │                   │
 │           │ messagebox │             │              │                   │
 │<──────────│            │             │              │                   │
 │  确认     │            │             │              │                   │
 │──────────>│            │             │              │                   │
 │           │ start 后台线程           │              │                   │
 │           │───────────>│             │              │                   │
 │           │            │ news(log,progress)          │                   │
 │           │            │────────────>│              │                   │
 │           │            │  run(...)   │              │                   │
 │           │            │────────────>│              │                   │
 │           │            │             │              │                   │
 │           │            │  (1) 校验 SSH 连接          │                   │
 │           │            │  (2) 检查存储路径 ──────────────────────────> │ test -d
 │           │            │             │<──────────────────────────────  │
 │           │            │  (3) 创建临时子目录 ──────────────────────────> │ mkdir -p
 │           │            │  (4) 解析config.json ────────────────────────> │ cat config.json
 │           │            │             │              │ 计算 shard_size  │
 │           │            │             │              │ _number          │
 │           │            │  (5) 上传包 ─────────────────────────────────> │ upload .tar.gz
 │           │            │             │              │                  │ upload .whl
 │           │            │  (6) 解压tar.gz ─────────────────────────────> │ tar -xzf
 │           │            │             │              │ find *.whl       │
 │           │            │  (7) 创建容器 ───────────────────────────────> │ docker run -d
 │           │            │             │              │   --gpus all     │
 │           │            │             │              │   -v model:model │
 │           │            │             │              │   -v storage:storage
 │           │            │             │              │   -v /tmp/pkgs   │
 │           │            │  (8) 安装wrapt ──────────────────────────────> │ docker exec pip
 │           │            │  (9) 安装UCM  ───────────────────────────────> │ docker exec pip
 │           │            │ (10) 上传bench脚本 ───────────────────────────> │ upload ucm_bench
 │           │            │ (11) 执行bench  ──────────────────────────────> │ docker exec
 │           │            │             │              │   python3         │
 │           │            │             │              │   ucm_bench.py    │
 │           │            │             │              │   --worker-num tp │
 │           │            │             │              │   --shard-size X  │
 │           │            │             │              │   ...             │
 │           │            │             │<────────────────── JSON结果 ─────│
 │           │            │ (12) 停止容器 ───────────────────────────────> │ docker stop
 │           │            │ (13) 清除临时目录 ────────────────────────────> │ rm -rf
 │           │            │             │              │                   │
 │           │            │ (14) 保存结果JSON到本地 output_dir              │
 │           │            │             │              │                   │
 │           │ _on_finish(result) via self.after()       │                   │
 │           │<───────────│             │              │                   │
 │           │ 显示 Dump BW / Load BW   │              │                   │
 │<──────────│            │             │              │                   │
```

### 3.3 Step 1 容器内 Benchmark 子流程 (ucm_bench.py)

```
主进程                     Worker 0 ... Worker N-1         UcmPipelineStore
 │                          │                │                  │
 │ create_store() x N       │                │                  │
 │ make_array() x N         │                │                  │
 │                          │                │                  │
 │ Barrier(N) wait ────────────────────────────────────────────│
 │                          │ barrier.wait   │ barrier.wait     │
 │                          │<────同步───────>│                  │
 │                          │                │                  │
 │ ┌── dump epoch 0 ────────────────────────────────────────── │
 │ │ ┌ for shard 0..S-1 │                │                     │
 │ │ │  store.dump_data(block_ids, idxes, ptrs)                │
 │ │ │                 │─────────────────────────────────────>│
 │ │ │  store.wait(task)                                       │
 │ │ │                 │<─────────────────────────────────────│
 │ │ │  cost = time.perf_counter() - tp                        │
 │ │ └ end for                                                 │
 │ │ 计算 bw = total_size / cost / 1e9                         │
 │ │ 打印 epoch/worker/avg_cost/p99_cost/bw                   │
 │ └────────────────────────────────────────────────────────── │
 │ Barrier(N) wait ────────────────────────────────────────────│
 │                          │ barrier.wait   │ barrier.wait     │
 │ ... repeat for epochs 1..31 ...                             │
 │                          │                │                  │
 │ ┌── load epoch 0..31 (同dump结构) ──────────────────────── │
 │ └────────────────────────────────────────────────────────── │
 │                          │                │                  │
 │ result_queue    <─────── worker_results (dump+load costs)   │
 │ Aggregation: 所有 worker 的 costs 合并计算                  │
 │ 输出 JSON 到 --output 文件                                  │
```

### 3.4 Step 2: TTFT 测试

```
用户       Step2Panel    后台线程    TTFTTestController     vLLM API Service
 │            │            │                │                      │
 │  Execute   │            │                │                      │
 │───────────>│            │                │                      │
 │            │ 校验       │                │                      │
 │            │ SSH/URL/Path/Name           │                      │
 │            │ start 后台线程              │                      │
 │            │───────────>│                │                      │
 │            │            │ run_online()   │                      │
 │            │            │───────────────>│                      │
 │            │            │                │ GET /health ────────>│
 │            │            │                │<──── 200 OK ────────│
 │            │            │                │                      │
 │            │            │                │ (Cold)               │
 │            │            │                │ POST /v1/completions│
 │            │            │                │ stream=True ────────>│
 │            │            │                │<── data: {...} ─────│
 │            │            │                │ time_to_first_token  │
 │            │            │                │                      │
 │            │            │                │ (Warmup)             │
 │            │            │                │ POST /v1/completions│
 │            │            │                │ (warm cache) ───────>│
 │            │            │                │                      │
 │            │            │                │ (Hot)                │
 │            │            │                │ POST /v1/completions│
 │            │            │                │ stream=True ────────>│
 │            │            │                │<── data: {...} ─────│
 │            │            │                │ measure HBM TTFT     │
 │            │            │                │                      │
 │            │            │                │ save_results(JSON)   │
 │            │            │<───────────────│                      │
 │            │ _on_finish via after()       │                      │
 │            │<───────────│                │                      │
 │            │ 显示 Full TTFT / HBM TTFT   │                      │
 │<───────────│            │                │                      │
```

### 3.5 Step 3: 收益分析

```
用户       Step3Panel                Analyzer
 │            │                         │
 │  Analyze   │                         │
 │───────────>│                         │
 │            │ 校验数字输入             │
 │            │                         │
 │            │ 可选: From Step1 按钮    │
 │            │ step1_panel.get_bandwidth()
 │            │                         │
 │            │ 可选: From Step2 按钮    │
 │            │ step2_panel.get_full_ttft()
 │            │ step2_panel.get_hbm_ttft()
 │            │                         │
 │            │ Analyzer.analyze()      │
 │            │────────────────────────>│
 │            │                         │  输入: bandwidth_gbs
 │            │                         │        full_prefill_ttft_ms
 │            │                         │        hbm_pc_ttft_ms
 │            │                         │
 │            │                         │  计算: ucm_min = hbm_pc (or full*0.1)
 │            │                         │        ucm_max = full (or hbm_pc*10)
 │            │                         │        ucm_avg = (min+max)/2
 │            │                         │        ttft_ratio = full/hbm_pc
 │            │                         │
 │            │  返回 result dict       │
 │            │<────────────────────────│
 │            │                         │
 │            │ 显示: TTFT Range        │
 │            │       Avg TTFT          │
 │            │       TTFT Ratio        │
 │            │ 保存 JSON 到 output_dir │
 │<───────────│                         │
```

### 3.6 Demo Mode 流程

```
用户勾选 Demo Mode
       │
       ▼
_main_window.py :: _on_demo_toggle()
       │
       ├─► core/demo.py :: start_demo()
       │   └─► MockVLLMServer.start()
       │       └─► HTTPServer(127.0.0.1:8000) 启动守护线程
       │
       ├─► 预填 SSH 面板: host=localhost, user=demo, pwd=demo
       ├─► 预填 Step2:  service_url=http://127.0.0.1:8000
       └─► 预填 Step1:  ucm_pkg=demo-package.tar.gz, dep=wrapt-demo.whl,
                         storage=/tmp/demo_kvcache

用户点击 Connect
       │
       ▼
_main_window.py :: _handle_ssh()
       │
       ├─► if self._demo_mode: MockSSHClient()
       └─► else:               SSHClient() (真实连接)

MockSSHClient.execute(command) 根据命令模式返回模拟数据:
    docker images     → nvidia/cuda:12.1-vllm, vllm/vllm-openai:latest
    cat config.json   → 模拟 LLaMA config (32 layers, 8 KV heads, dim=128)
    docker run -d ...  → demo-container-001
    docker exec pip    → Successfully installed
    docker exec ucm_bench → 直接本地计算模拟 JSON 结果
    docker stop        → 空输出

用户执行 Step2:
    TTFTTestController 直接向 127.0.0.1:8000 发送 HTTP 请求
    MockVLLMServer 响应流式 completions (含延迟模拟)
```

### 3.7 i18n 语言切换流程

```
用户选择语言 ComboBox
       │
       ▼
_main_window.py :: _on_lang_change()
       │
       ▼
i18n.py :: set_lang("en" | "zh")
       │
       │  遍历所有 _listeners 回调:
       │
       ├─► MainWindow.refresh_language()
       │   ├─► 更新 window.title
       │   ├─► notebook.tab(step1, text=...)    "Step 1: 带宽测试" / "Step 1: Bandwidth Test"
       │   ├─► notebook.tab(step2, text=...)
       │   ├─► notebook.tab(step3, text=...)
       │   ├─► log_frame title
       │   └─► status label
       │
       ├─► SSHConnectionPanel.refresh_language()
       │   ├─► panel title, all labels, buttons
       │   └─► _update_state_text() 根据当前连接状态刷新
       │
       ├─► ScenarioParamsPanel.refresh_language()
       │   ├─► panel title, request_len label, concurrency label
       │
       ├─► Step1Panel.refresh_language()
       │   ├─► 所有 LabeledEntry.set_label()
       │   ├─► 所有 Button text
       │   ├─► docker_label, docker_refresh_btn
       │   ├─► _update_shard_info()
       │   └─► _format_result() (如有结果数据)
       │
       ├─► Step2Panel.refresh_language()
       │   ├─► 所有 LabeledEntry.set_label()
       │   ├─► 所有 Button text
       │   └─► _format_result()
       │
       └─► Step3Panel.refresh_language()
           ├─► hint_label text
           ├─► 所有 LabeledEntry.set_label()
           ├─► 所有 Button text
           └─► _format_result()
```

---

## 4. 关键设计决策

### 4.1 Panel 间数据传递模式

各 Panel 通过 `self.app` (MainWindow 引用) 互相访问，而非事件总线：

```
Step3Panel ───> self.app.step1_panel.get_bandwidth()
           ───> self.app.step2_panel.get_full_ttft()
Step1Panel ───> self.app.scenario_params.get_request_len()
Step2Panel ───> self.app.scenario_params.get_concurrency()
```

### 4.2 后台线程 + self.after() 模式

所有耗时操作（SSH、网络请求）在 `threading.Thread` 中执行，通过 `self.after(0, callback)` 安全地更新 UI。

### 4.3 组件自身管理 i18n

每个 Panel 的 `__init__` 中注册 `on_lang_change(self.refresh_language)`，语言切换时各组件的 `refresh_language()` 自动被调用，无需手动通知。

### 4.4 MockSSHClient 命令匹配

Demo 模式下通过字符串模式匹配 (`if "docker images" in command:`) 识别命令并返回模拟数据。新增命令只需添加匹配规则，不影响真实 SSH 逻辑。

### 4.5 进度回调模式

所有 Controller 接受 `log_callback` 和 `progress_callback`，实现与 UI 的解耦。Controller 不依赖任何 tkinter 组件。

### 4.6 config.json 自动解析

`parse_model_config()` 通过 SSH 读取远端 config.json，自动识别 GQA/MLA 模型类型并计算 shard_size：
- **GQA**：`num_kv_heads × head_dim × 2 × 128 × 2(element_size)`
- **MLA**：`(kv_lora_rank + qk_rope_head_dim) × 128 × 2`

### 4.7 临时目录隔离

带宽测试在存储路径下创建 `ucm_bench_<timestamp>` 临时子目录，测试完成后自动 `rm -rf` 清理，避免污染已有数据。

### 4.8 TP 并行支持

`ucm_bench.py` 使用 `multiprocessing.Barrier` 同步多个 worker 进程，每个 worker 在独立进程中执行 dump/load，通过 `multiprocessing.Queue` 汇聚结果。TP 数量从 Step1 UI 自动传入 `--worker-number`。

---

## 5. 文件清单

```
ucm_check_tool/
├── main.py                        # 程序入口
├── config.py                      # 全局路径/常量
├── i18n.py                        # 中英双语翻译 (189 keys)
├── build.spec                     # PyInstaller 构建配置
├── requirements.txt               # Python 依赖 (paramiko, requests)
├── README.md                      # 用户文档
├── DESIGN.md                      # 本文档
│
├── core/                          # 业务逻辑层
│   ├── ssh_client.py              # SSH 客户端 (paramiko)
│   ├── logger.py                  # 日志管理
│   ├── ucm_bandwidth.py           # UCM Store 带宽测试控制器
│   ├── ttft_test.py               # TTFT 测试控制器
│   ├── analyzer.py                # 收益分析器
│   ├── bandwidth_test.py          # (旧版) vLLM HTTP 带宽测试 (废弃)
│   └── demo.py                    # 本地演示模式 (MockSSH + MockVLLM)
│
├── gui/                           # 表现层 (Tkinter)
│   ├── widgets.py                 # 可复用UI组件
│   ├── main_window.py             # 主窗口
│   ├── step1_panel.py             # Step 1: 带宽测试
│   ├── step2_panel.py             # Step 2: TTFT 测试
│   └── step3_panel.py             # Step 3: 收益分析
│
├── remote_scripts/                # 远端容器内执行脚本
│   ├── ucm_bench.py               # UCM Store 带宽测试 (dump/load)
│   └── remote_bench.py            # (旧版) vLLM HTTP 测试 (废弃)
│
└── tests/                         # 单元测试 (pytest)
    ├── test_ssh_client.py
    ├── test_bandwidth_test.py
    ├── test_ttft_test.py
    └── test_analyzer.py
```
