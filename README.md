# UCM-Scout

UCM 运行环境带宽检测、TTFT 测试与收益分析工具。

## 下载与使用

### 方式一：直接使用已构建的 EXE（推荐）

从 [Releases 页面](https://github.com/student-jhz/ucm-scout/releases) 下载最新版 `ucm_check_tool.exe`，直接双击运行，**无需安装 Python 环境**。

### 方式二：通过源码运行

需要 Python 3.9+ 环境：

```bash
pip install -r requirements.txt
python main.py
```

### 方式三：自行构建 EXE

```bash
# 1. 下载 UCM 源码（构建前执行一次，固定下载 UCM tag v0.6.0）
python scripts/download_ucm.py

# 2. 安装 PyInstaller 并构建
pip install pyinstaller
pyinstaller build.spec --clean
```

构建产物位于 `dist/UCM-Scout.exe`。

## 界面说明

启动后窗口从上到下依次为：

| 区域 | 说明 |
|------|------|
| SSH 连接面板 | 输入 Linux 主机地址、端口、用户名、密码，点击 **Connect** |
| 场景参数 | 填写**请求长度**和**并发数**（Step1 与 Step2 共用，需先于 Step1 填写） |
| Step1 标签页 | 带宽测试 |
| Step2 标签页 | TTFT 测试 |
| Step3 标签页 | UCM PC 收益分析 |
| 全局日志 | 汇总所有步骤的运行日志 |

## 操作流程

### Step1 — 带宽测试

1. 确保顶部 SSH 已连接（显示绿色 "connected"）
2. 填写模型权重目录 → 自动解析 `config.json`，计算 `shard_size` 和 `shard_number`
3. 点击 **Refresh** 获取远端 Docker 镜像列表（自动过滤 vllm 相关镜像）
4. 选择依赖包（`.whl`，如 `wrapt-1.17.2-*.whl`）
5. 填写存储后端路径
6. 点击 **Execute Bandwidth Test**

> UCM 源码及其 C++ 编译依赖（fmt, spdlog, pybind11, zlib）已打包在 EXE 内，运行时会自动上传到远端容器并从源码编译安装（无需再选择 `.tar.gz` 包）。

程序自动：上传源码+依赖 → 创建临时容器 → 挂载模型/存储路径 → pip 安装 wrapt → 从源码编译安装 UCM → 执行 `dump_data`/`load_data` 测量 KV cache 读写带宽 → 清理容器

> 带宽测试使用 UCM 底层存储引擎（Posix + AIO），测量 `shard_size × shard_number × block_number` 的 IO 吞吐。

### Step2 — TTFT 测试

填写服务 URL、模型路径、模型名，点击 **Execute TTFT Test**，程序分别测试完全 prefill 计算的 TTFT 和 HBM PC 命中的 TTFT。

### Step3 — 收益分析

1. 填写带宽（可从 Step1 结果自动回填，点击 **From Step1**）
2. 填写 TTFT 值（可从 Step2 结果自动回填，点击 **From Step2**）
3. 点击 **Analyze**
4. 查看以下结论：
   - **UCM PC TTFT Range**：UCM PC 场景下 TTFT 的预期范围
   - **Avg UCM PC TTFT**：UCM PC 场景下的平均 TTFT
   - **TTFT Ratio**：完全重算 vs HBM PC 的 TTFT 比值

## 结果文件

所有结果自动保存在 `./results/` 目录，日志保存在 `./logs/` 目录：

```
results/
├── step1/bandwidth_result.json
├── step2/ttft_result.json
└── step3/analysis_result.json

logs/YYYYMMDD_HHMMSS.log
```
