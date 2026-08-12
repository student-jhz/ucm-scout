# UCM-Scout

[![Docs](https://img.shields.io/badge/Docs-Documentation-blue)](https://student-jhz.github.io/ucm-scout/)

A tool for UCM runtime environment bandwidth testing, TTFT testing, and benefit analysis.

## Download & Usage

### Method 1: Use the prebuilt EXE (recommended)

Download the latest version from the repository's `dist/UCM-Scout.exe` and double-click to run. No Python environment needed.

### Method 2: Build the EXE yourself

```bash
# 1. Download the UCM source (run once before building; pins UCM tag v0.6.0)
python scripts/download_ucm.py

# 2. Install PyInstaller and build
pip install pyinstaller
pyinstaller build.spec --clean
```

The build artifact is `dist/UCM-Scout.exe`.

## Interface Overview

After launch, the window contains the following sections from top to bottom:

| Section | Description |
|---------|-------------|
| SSH connection panel | Enter Linux host address, port, username, password; click **Connect** |
| Scenario parameters | Fill in **request length** and **concurrency** (shared by Step1 and Step2; fill in before Step1) |
| Step1 tab | Bandwidth test |
| Step2 tab | TTFT test |
| Step3 tab | UCM PC benefit analysis |
| Global log | Aggregates runtime logs from all steps |

## Workflow

### Step1 — Bandwidth Test

1. Ensure the SSH connection at the top is connected (shows green "connected")
2. Fill in the model weight directory → automatically parses `config.json` to compute `shard_size` and `shard_number`
3. Click **Refresh** to get the remote Docker image list (automatically filters vllm-related images)
4. Select a dependency package (`.whl`, e.g. `wrapt-1.17.2-*.whl`)
5. Fill in the storage backend path
6. Click **Execute Bandwidth Test**

> The UCM source and its C++ build dependencies (fmt, spdlog, pybind11, zlib) are bundled inside the EXE. They are uploaded to the remote container and compiled from source at runtime (no need to select a `.tar.gz` package).

The program automatically: uploads source + dependencies → creates a temporary container → mounts model/storage paths → pip installs wrapt → compiles and installs UCM from source → runs `dump_data`/`load_data` to measure KV cache read/write bandwidth → cleans up the container.

> The bandwidth test uses the UCM lower-level storage engine (Posix + psync) to measure IO throughput of `shard_size × shard_number × block_number`.

### Step2 — TTFT Test

Fill in the service URL, model path, and model name; click **Execute TTFT Test**. The program measures the TTFT for full prefill computation and the HBM PC cache hit scenario separately.

### Step3 — Benefit Analysis

1. Fill in bandwidth (can be auto-filled from the Step1 result by clicking **From Step1**)
2. Fill in the TTFT values (can be auto-filled from the Step2 result by clicking **From Step2**)
3. Click **Analyze**
4. View the following conclusions:
   - **UCM PC TTFT Range**: expected TTFT range in the UCM PC scenario
   - **Avg UCM PC TTFT**: average TTFT in the UCM PC scenario
   - **TTFT Ratio**: the TTFT ratio of full recompute vs HBM PC

## Result Files

All results are saved automatically to `./results/`, and logs to `./logs/`:

```
results/
├── step1/bandwidth_result.json
├── step2/ttft_result.json
└── step3/analysis_result.json

logs/YYYYMMDD_HHMMSS.log
```
