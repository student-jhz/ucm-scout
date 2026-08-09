---
name: dev-task
description: 用于"需求开发/问题解决"场景。当用户提出本 UCM-Scout 项目的新需求（如新功能、改动、优化）或反馈已有 bug/问题时触发。执行标准开发流程：分析审核需求 → 开发 → 按需补充/更新 unittest 测试用例 → 自验证 → 更新 README/AGENTS 文档 → 构建 EXE → 提交代码 → 推送到远端。Use when the user asks to implement a new feature, fix a bug, or resolve an issue in this project.
---

# 需求开发 / 问题解决流程（UCM-Scout）

本 skill 用于 UCM-Scout 项目的**新需求开发**和**已有问题解决**。当用户描述一个功能需求、改进、或 bug 时，严格按下述流程逐步执行，不要跳步。

## 适用范围

- 用户在 .opencode 会话中提出新功能/优化/改动需求
- 用户反馈 bug、错误、异常行为，请求修复
- 用户要求"按流程走一遍"或提及"开发/解决问题"

本 skill **不**适用于：纯提问咨询、仅查看代码、构建 EXE 后不回退等非开发类请求。

## 流程总览

1. 分析审核需求
2. 开发实现
3. 按需补充/更新测试用例
4. 自验证
5. 更新 .md 文档
6. 构建 EXE 程序
7. 提交代码
8. 推送远端

每个阶段完成并确认后再进入下一阶段。

## 阶段 1：分析审核需求

- 先阅读 `README.md`、`AGENTS.md` 及相关模块源码（`core/`、`gui/`、`remote_scripts/`），理解现状。
- 用 todowrite 建立任务清单，包含上面 8 个阶段。
- 澄清需求细节：影响哪个 Step / 哪个面板 / 哪些文件；是否涉及 i18n、Demo 模式、SSH/Docker 逻辑。
- **先给出实现方案**交给用户审核，用户确认后再动手开发，不要直接改代码。

## 阶段 2：开发实现

- 遵循项目约定：
  - `core/` = 业务逻辑（不得依赖 UI/Tkinter）；`gui/` = 呈现层（Tkinter）
  - Tkinter 显式导入：`from tkinter import messagebox, filedialog`
  - 面板间通过 `self.app`（MainWindow 引用）通信，如 `self.app.step1_panel.get_bandwidth()`
  - 资源路径用 `config.py` 的逻辑（PyInstaller 下用 `sys._MEIPASS`），不要用 `__file__`
  - SSH 连接超时 10s，命令超时 600s（`DEFAULT_COMMAND_TIMEOUT`）
  - 新增 UI 文案需在 `i18n.py` 补充翻译，并让对应面板注册 `on_lang_change(self.refresh_language)`
  - Demo 模式：若改动涉及 SSH/HTTP 操作，需同步 MockSSHClient/MockVLLMServer 支持
- 不加多余注释；保持与既有代码风格一致。

## 阶段 3：按需补充/更新测试用例

- 项目用 **unittest**（不是 pytest），测试在 `tests/` 目录。
- 对新增/改动的业务逻辑，在 `tests/` 下补充或更新对应 `test_*.py`，用 `unittest.mock.patch` 模拟 SSH/HTTP 操作。
- 若改动不涉及业务逻辑（如纯 GUI 排版），可跳过。

## 阶段 4：自验证

- 运行全部测试：
  ```bash
  python -m unittest discover -s tests -v
  ```
- 修复所有失败用例；若无失败，运行 `python main.py` 做一次冒烟验证（Demo 模式），确认无运行时错误。

## 阶段 5：更新 .md 文档

- 如功能/用法有变化，更新 `README.md`（操作流程、界面说明、结果文件等）。
- 如架构/约束/排障有变化，更新 `AGENTS.md`。
- 本 skill 内容如需同步，也一并更新。

## 阶段 6：构建 EXE 程序

- 构建前若 `ucm_src/` 未下载，先执行：
  ```bash
  python scripts/download_ucm.py
  ```
- 构建：
  ```bash
  pip install pyinstaller
  pyinstaller build.spec --clean
  ```
- 产物位于 `dist/UCM-Scout.exe`。确认构建成功、产物存在。

## 阶段 7：提交代码

- 先查看改动：`git status`、`git diff`、`git log --oneline -5`。
- 只暂存本次相关文件，不提交无关文件、机密。
- 用符合仓库风格的中文简洁提交信息提交。
- 若 `dist/UCM-Scout.exe` 需入库（按 AGENTS.md 约定），用 `git add -f dist/UCM-Scout.exe` 一并提交。

## 阶段 8：推送到远端

- 推送到远端 main 分支：
  ```bash
  git push origin main
  ```
- 确认推送成功。

## 关键约定（来自 AGENTS.md，务必遵守）

- EXE 必须提交到仓库（`git add -f dist/UCM-Scout.exe`），不要因 gitignore 而遗漏。
- 每次提交、推送前先检查 `git status`；不要提交 secrets。
- 只有用户明确要求时才进行提交/推送；本 skill 的提交阶段执行前，若项目尚未明确授权，先询问用户是否提交。

## 收尾

- 更新 todo：将完成的阶段标记为 completed。
- 向用户汇报：改动文件、测试结果、构建结果、提交/推送情况。
