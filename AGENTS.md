# AGENTS.md - OpenCode Instructions for UCM-Scout

## Project Overview

Python 3.9+ Tkinter GUI tool for UCM (Unified Cache Manager) bandwidth testing and TTFT analysis. Tests remote Linux hosts via SSH/Docker containers and analyzes KV cache performance.

## Key Commands

```bash
# Run application
python main.py

# Run tests (unittest framework)
python -m unittest discover -s tests -v

# Build standalone EXE
pip install pyinstaller
pyinstaller build.spec --clean
# Output: dist/UCM-Scout.exe
```

**IMPORTANT**: After every commit, rebuild EXE and commit it to repository using:
```bash
pyinstaller build.spec --clean
git add -f dist/UCM-Scout.exe
git commit -m "Update UCM-Scout.exe"
git push origin main
```

## Architecture

```
main.py → gui/main_window.py (Tk GUI)
         ├── gui/step1_panel.py → core/ucm_bandwidth.py (Docker + UCM Store test)
         ├── gui/step2_panel.py → core/ttft_test.py (vLLM API TTFT test)
         └── gui/step3_panel.py → core/analyzer.py (UCM PC profit analysis)
         
core/ = business logic (no UI dependencies)
gui/ = presentation layer (Tkinter)
remote_scripts/ = uploaded to container for execution
```

**Panel communication**: Panels access each other via `self.app` (MainWindow reference), e.g., `self.app.step1_panel.get_bandwidth()`

## Non-Obvious Details

### Three-Step Flow

1. **Step 1 (Bandwidth)**: SSH → parse remote `config.json` (auto-calc shard_size/shard_number) → upload UCM packages → create Docker container → run `ucm_bench.py` → cleanup
2. **Step 2 (TTFT)**: HTTP POST to vLLM `/v1/completions` (streaming) → measure time to first token for cold (full prefill) and hot (HBM PC hit) scenarios
3. **Step 3 (Analysis)**: Uses bandwidth + TTFT data to calculate UCM PC performance range

### Shard Size Calculation

- **GQA models**: `num_kv_heads × head_dim × 2 × 128 × 2`
- **MLA models**: `(kv_lora_rank + qk_rope_head_dim) × 128 × 2`

Auto-detected from remote `config.json` via SSH.

### Docker Device Handling

Code auto-detects Ascend vs GPU:
- **GPU**: `--gpus all`
- **Ascend**: `--device /dev/davinci*` + mount Ascend driver libs

### Temp Directory Pattern

Step 1 creates `<storage_path>/ucm_bench_<timestamp>/` and **always** cleans up (`rm -rf`) even on failure.

### PyInstaller Resource Paths

After PyInstaller build, resources use `sys._MEIPASS` (see `config.py`). Do NOT use `__file__` for resource paths.

## Important Constraints

- SSH connection timeout: 10s (hardcoded in `SSHClient.connect(timeout=10)`)
- Command timeout: 600s (`DEFAULT_COMMAND_TIMEOUT` in `config.py`)
- Tkinter imports must be explicit: `from tkinter import messagebox, filedialog` (not auto-included)
- Combobox `width` visually differs from Entry due to dropdown button

## Demo Mode

Check "Demo Mode" checkbox to:
- Start local `MockVLLMServer` on `127.0.0.1:8000`
- Use `MockSSHClient` (pattern-matches commands like `"docker images" in cmd`)
- Pre-fill all fields with demo values
- No real SSH/vLLM required for testing

## Output Locations

```
results/
├── step1/bandwidth_result.json
├── step2/ttft_result.json
└── step3/analysis_result.json

logs/YYYYMMDD_HHMMSS.log
```

Both directories are gitignored.

## i18n

189 translation keys in `i18n.py`. Each panel registers `on_lang_change(self.refresh_language)` for automatic refresh. No manual notification needed.

## Common Pitfalls

- **Missing validation**: Add `messagebox.showwarning` at start of `_on_run()` methods to validate required fields
- **Progress bar stuck**: Reset progress to 0 in `_on_finish()` callback
- **pip install tar.gz wrong**: Must `tar -xzf` → `find *.whl` → `pip install *.whl`
- **Queue + docker exec result loss**: Use file-based result passing (worker writes JSON, main process reads)
- **Real-time output missing**: Add `PYTHONUNBUFFERED=1 stdbuf -oL` to docker exec commands
- **libmetrics.so not found**: Set `LD_LIBRARY_PATH` in container environment

## Testing

Uses `unittest` (not pytest). All tests in `tests/` directory. Mock pattern: `unittest.mock.patch` for SSH/HTTP operations.

## Build Artifacts

`build/` and `dist/` are gitignored. However, **EXE must be committed to repository** using `git add -f dist/UCM-Scout.exe` after every code change.