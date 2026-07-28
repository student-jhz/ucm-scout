# UCM-Scout Agent Handoff

## 项目概览

UCM-Scout 是一个 **UCM (Unified Cache Manager) 带宽测试与 TTFT 收益分析工具**，用于在远程 Linux 主机上通过 Docker 容器测试 KV cache 的读写带宽，并分析 UCM PC（外存前缀缓存命中）的收益。

- **语言**：Python 3.9，Tkinter GUI
- **依赖**：paramiko (SSH), requests (HTTP)
- **打包**：PyInstaller → 单文件 EXE
- **仓库**：`git@github.com:student-jhz/ucm-scout.git`

---

## 用户画像

- 用户是 UCM 项目开发者，熟悉 KV cache、存储系统、AI 推理
- 说话直接，会指出问题并要求修复
- 会提具体技术需求，也会说"对齐一下"之类的 UI 调整
- 有个关联项目在 `D:\code\unified-cache-management`

---

## 项目结构

```
ucm_check_tool/
├── main.py                     # 入口
├── config.py                   # 路径常量 (含 PyInstaller 适配)
├── i18n.py                     # 中英双语 (189 keys), Translator 类
├── build.spec                  # PyInstaller 构建配置
├── README.md                   # 用户文档
├── DESIGN.md                   # 架构文档 + 时序图
│
├── core/                       # 业务逻辑层 (无 UI 依赖)
│   ├── ssh_client.py           # SSH 客户端 (paramiko)
│   ├── logger.py               # 日志管理
│   ├── ucm_bandwidth.py        # ≡ Step1 后端: Docker + UCM Store 带宽测试
│   ├── ttft_test.py            # ≡ Step2 后端: vLLM API TTFT 测试
│   ├── analyzer.py             # ≡ Step3 后端: UCM PC 收益分析
│   ├── bandwidth_test.py       # (废弃) 旧版 vLLM HTTP 带宽测试
│   └── demo.py                 # 本地演示: MockSSHClient + MockVLLMServer
│
├── gui/                        # 表现层 (Tkinter)
│   ├── widgets.py              # ScrollableLogFrame, LabeledEntry, SSHPanel, RemoteDirBrowser
│   ├── main_window.py          # 主窗口: 三个 Tab, Demo 模式, 语言切换
│   ├── step1_panel.py          # Step 1: 带宽测试 (Docker 镜像选择, UCM 包上传...)
│   ├── step2_panel.py          # Step 2: TTFT 测试 (vLLM API 请求)
│   └── step3_panel.py          # Step 3: 收益分析 (UCM PC pipeline 模型)
│
├── remote_scripts/             # 上传到远端容器执行的独立脚本
│   ├── ucm_bench.py            # UCM Store 带宽测试 (dump_data/load_data)
│   └── remote_bench.py         # (废弃) 旧版 vLLM benchmark
│
├── tests/                      # pytest
│   ├── test_analyzer.py
│   ├── test_bandwidth_test.py
│   ├── test_ssh_client.py
│   └── test_ttft_test.py
│
└── logs/, results/             # 运行时生产 (gitignored)
```

---

## 三个 Step 的完整流程

### Step 1: 带宽测试

```
SSH 连接 → 解析 config.json (shard_size/number 自动计算)
         → 刷新 Docker 镜像列表 (docker images | grep vllm)
         → 用户选择镜像 + 上传 UCM tar.gz + wrapt whl
         → 存储路径确认 (弹窗告知会创建临时目录并清理)
         → 执行:
           1. test -d 检查存储路径
           2. mkdir -p 创建临时子目录 ucm_bench_<timestamp>
           3. cat config.json → 计算 shard_size, shard_number
           4. upload .tar.gz + .whl → /tmp/ucm_pkgs/
           5. tar -xzf 解压 → find *.whl
           6. docker run 创建容器 (挂载 model, storage, pkgs)
           7. pip install wrapt.whl
           8. pip install ucm whl
           9. upload ucm_bench.py
          10. docker exec bash -c 'PYTHONUNBUFFERED=1 python3 ucm_bench.py ...'
          11. docker stop + rm -rf 清理临时目录
          12. 读取 JSON 结果 → 保存本地
```

**shard_size 计算**：GQA = `num_kv_heads × head_dim × 2 × 128 × 2`，MLA = `(kv_lora_rank + qk_rope_head_dim) × 128 × 2`

**TP 数量** → `--worker-number`，控制 ucm_bench.py 的多进程并行度

### Step 2: TTFT 测试

```
POST /v1/completions (stream=True), 记录 t0
解析 SSE 响应，第一条 data: {...} 的时间 t1
TTFT = (t1 - t0) × 1000 ms

Cold: warmup=False → Full Prefill TTFT
Warm: 先 warmup_cache() 一次 → HBM PC TTFT
```

### Step 3: 收益分析

基于 UCM PC pipeline 模型：

```
t_compute_per_layer = hbm_pc_ttft / num_layers
t_io_per_layer = bytes_per_layer / bw_ssd + bytes_per_layer / bw_pcie

if t_io_per_layer <= t_compute_per_layer:
    ucm_ttft = hbm_pc_ttft + t_io_per_layer      ← IO 被计算隐藏
else:
    ucm_ttft = t_io_total + t_compute_per_layer  ← IO 瓶颈

is_beneficial = ucm_ttft < full_prefill_ttft
```

---

## Demo 模式

勾选 Demo Mode → `start_demo()` 启动本地 `MockVLLMServer(127.0.0.1:8000)` + `MockSSHClient` 模拟所有 SSH 命令返回假数据。预填所有字段（localhost, demo, demo），无需真实远端环境即可走完整流程。

---

## 关键架构决策

1. **Panel 间通信**：通过 `self.app` (MainWindow 引用) 直接访问，如 `self.app.step1_panel.get_bandwidth()`
2. **后台线程模式**：耗时操作在 `threading.Thread` 中，通过 `self.after(0, callback)` 更新 UI
3. **i18n 自管理**：每个 Panel 注册 `on_lang_change(self.refresh_language)`，无需手动通知
4. **MockSSH 命令匹配**：字符串模式匹配（`if "docker images" in cmd:`），易扩展
5. **临时目录隔离**：`ucm_bench_<timestamp>` 子目录，失败也会 `rm -rf` 清理

---

## 真实环境适配（2026-07 修复）

| 问题 | 修复 |
|------|------|
| `--gpus all` 昇腾不支持 | `_detect_device_type()` 自动检测 → Ascend 用 `--device /dev/davinci*` |
| Ascend 驱动卷缺失 | 挂载 `/usr/local/Ascend/driver/lib64/` 等 |
| `spawn` 导致 SemLock 报错 | 移除 `set_start_method("spawn")`，用默认 fork |
| `Queue` + `docker exec` 结果丢失 | 改为文件传递 (worker JSON → 主进程读取汇总) |
| `libmetrics.so` 找不到 | 设置 `LD_LIBRARY_PATH` |
| 输出不实时 | `PYTHONUNBUFFERED=1 stdbuf -oL` |

---

## 构建 EXE

```bash
pip install pyinstaller
pyinstaller build.spec --clean
# 产物: dist/UCM-Scout.exe
```

---

## 执行测试

```bash
pip install pytest  # (如果未安装)
python -m pytest tests/ -v
# 共 25 个测试
```

---

## Git 提交流程

```bash
git add -A
git commit -m "..."
git push origin main
# SSH: git@github.com:student-jhz/ucm-scout.git
```

---

## 用户常见问题 & 解决模式

| 用户反馈 | 解决方式 |
|---------|---------|
| "栏框没对齐" | 统一 LabeledEntry 的 `label_width` 为相同值 |
| "XX 字段显示不全" | 增大 `label_width` 或添加缺失的标签 |
| "进度卡住不失败" | 在 `_on_finish()` 里重置 progress 为 0 |
| "未填参数也能执行" | 在 `_on_run()` 开头加 `messagebox.showwarning` 校验 |
| "pip install tar.gz 不对" | 改为 tar -xzf → find *.whl → pip install whl |
| "Docker 镜像选不了" | Combobox 改为 editable + KeyRelease 筛选 |
| "模型路径要远端选" | RemoteDirBrowser (SSH `ls -1p` 浏览远端目录) |
| "存储路径需确认" | `messagebox.askyesno` + 临时目录自动清理 |
| "Step3 分析逻辑不对" | 重写为 UCM PC pipeline 带宽模型 |

---

## 注意事项

- PyInstaller 打包后需 `sys._MEIPASS` 获取资源路径 (`config.py`)
- `from tkinter import messagebox, filedialog` 需从 tkinter 显式导入，不会自动包含
- Combobox vs Entry 的 `width` 参数：Combobox 有下拉按钮，视觉上比同 width 的 Entry 略宽
- SSH 连接超时默认 10s，通过 `SSHClient.connect(timeout=10)` 传入
- `build/` 和 `dist/` 已被 `.gitignore`，不提交 EXE 到仓库
