# UCM Check Tool

UCM运行环境带宽检测、TTFT测试与收益分析工具。

## 快速开始

```bash
pip install -r requirements.txt
python main.py
```

## 界面说明

启动后窗口从上到下依次为：

| 区域 | 说明 |
|------|------|
| SSH连接面板 | 输入Linux主机地址、端口、用户名、密码，点击 **Connect** |
| 场景参数 | 填写**请求长度**和**并发数**（Step1与Step2共用，需先于Step1填写） |
| Step1 标签页 | 带宽测试 |
| Step2 标签页 | TTFT测试 |
| Step3 标签页 | UCM PC收益分析 |
| 全局日志 | 汇总所有步骤的运行日志 |

## 操作流程

### Step1 — 带宽测试

1. 确保顶部SSH已连接（显示绿色 "connected"）
2. 填写以下参数：

| 参数 | 说明 | 示例 |
|------|------|------|
| Model Weight Dir | 远端模型权重目录 | `/models/llama-7b` |
| DP Count | 数据并行数量 | `1` |
| TP Count | 张量并行数量 | `1` |
| KV Cache Dir | KV Cache保存目录 | `/data/kvcache` |
| Output Dir | 结果输出目录（本地） | `./results/step1` |

3. 点击 **Execute Bandwidth Test**
4. 观察进度条和实时日志，等待执行完成
5. 底部显示 **实际带宽 (GB/s)**

> 原理：通过SSH在远端启动vLLM服务并发送benchmark请求，测量实际内存带宽。

### Step2 — TTFT测试

**在线模式**（有已运行的服务）：
1. 选择 **Online**
2. 填写服务URL、模型路径、模型名
3. 点击 **Execute TTFT Test**
4. 程序分别测试完全prefill计算的TTFT和HBM PC命中的TTFT

**离线模式**（无服务，人工录入）：
1. 选择 **Offline**
2. 手动填写完全prefill TTFT和HBM PC TTFT（毫秒）
3. 点击 **Confirm Offline Values** 保存

### Step3 — 收益分析

1. 填写带宽（可从Step1结果自动回填，点击 **From Step1**）
2. 填写TTFT值（可从Step2结果自动回填，点击 **From Step2**）
3. 点击 **Analyze**
4. 查看以下结论：
   - **UCM PC TTFT Range**：UCM PC场景下TTFT的预期范围
   - **Avg UCM PC TTFT**：UCM PC场景下的平均TTFT
   - **TTFT Ratio**：完全重算vs HBM PC的TTFT比值

## 结果文件

所有结果自动保存在 `./results/` 目录，日志保存在 `./logs/` 目录：

```
results/
├── step1/bandwidth_result.json
├── step2/ttft_result.json
└── step3/analysis_result.json

logs/YYYYMMDD_HHMMSS.log
```
