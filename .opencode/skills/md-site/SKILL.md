---
name: md-site
description: 用于"搭建/更新 UCM-Scout 多语言文档网站（GitHub Pages）"场景。当用户要为项目搭建展示中英文 README/文档的网页、为 GitHub Pages 新增/更新文档页面、或切换/修复文档语言时触发。执行标准流程：确认文档内容 → 创建多语言 README → 生成 docs/index.html 中英切换单页 → 本地预览验证 → 提交推送 → 启用/校验 GitHub Pages。Use when the user asks to build a documentation website, add multilingual doc pages, or set up GitHub Pages for this project.
---

# 多语言文档网站 / GitHub Pages 流程（UCM-Scout）

本 skill 用于 UCM-Scout 项目的**文档网页展示**和 **GitHub Pages 站点**搭建与维护。当用户想把项目 README/文档做成一个中英文可切换的网页时，严格按下述流程执行。

## 适用范围

- 用户要求"搭建一个网站/网页展示 README 文档"
- 用户要求"展示中英文文档"
- 用户要求"启动/配置 GitHub Pages"
- 用户要求"更新文档站点、新增语言、修复语言切换"

本 skill **不**适用于：普通界面多语言（那是 `i18n.py` 的翻译 key 机制）、纯提问、修改应用功能逻辑。

## 要点：界面翻译 vs 文档翻译

- **界面翻译**：GUI 控件的短文案，定义在 `i18n.py` 的 `_translations` 字典（en/zh 两套 key），运行时经 `tr("key")` 读取。**文档页面不需要**走这套机制。
- **文档翻译**：静态长文本，中文/英文各自维护一份内容，靠页面切换展示。**不要为文档写 i18n key**。

## 流程总览

1. 确认文档内容与语言要求
2. 维护多语言 README（`README.md` / `README.en.md`）
3. 生成 `docs/index.html` 中英切换单页
4. 本地预览验证
5. 提交推送
6. 启用/校验 GitHub Pages

## 阶段 1：确认文档内容与语言要求

- 用 glob 查看现有 `.md` 与 `docs/` 结构。
- 明确：需要哪些语言（目前中文 + 英文）、内容来源（通常是 `README.md`）、是否嵌入到单页还是分文件。
- 用 todowrite 建立任务清单（含上述 6 个阶段）。

## 阶段 2：维护多语言 README

- 中文：沿用现有 `README.md`；英文：创建 `README.en.md`（逐节对照翻译）。
- 仓库根目录放 `README.md`（GitHub 自动渲染）和 `README.en.md`，两者作为文档的「源文件」。

## 阶段 3：生成 `docs/index.html` 中英切换单页

- 在 `docs/` 目录创建 `index.html` —— GitHub Pages 会把 `/docs` 当作站点根，`index.html` 是首页。
- 结构要求：
  - 一个 `<header>`：左侧品牌名，右侧语言切换按钮（`中文` / `English`）。
  - `<main>` 内两个 `<section>`：`id="content-zh"` 和 `id="content-en"`，分别放中英文内容。
  - 内嵌 `<script>` 实现切换：
    - 用 `display:none` 隐藏非当前语言块。
    - 用 `localStorage` 记住语言偏好（key 自定义，如 `ucm_scout_lang`）。
    - 高亮当前语言按钮。
  - 内联 `<style>`，提供基础排版（标题、表格、代码块、引用），移动端自适应（媒体查询）。
- 语言切换**不用哈希路由**，纯 JS 切换两个 section 即可，简单且无需服务器。
- 内容如有代码块/表格/`>` 引用，在 HTML 中分别用 `<pre><code>`、`<table>`、`<blockquote>` 呈现；`&`、`<`、`>` 需转义（如 `&amp;`）。
- 若以后文档变长，可改为两份独立页面 + 链接跳转，但当前单页足够。

## 阶段 4：本地预览验证

- 直接双击打开 `docs/index.html`（或本地起静态服务器 `python -m http.server`）验证：
  - 中文/英文默认显示正常。
  - 点击切换按钮能正确切换内容与按钮高亮。
  - 刷新后语言偏好能记住（localStorage）。
- 检查 README.en.md 内容与中文对应、无遗漏章节。

## 阶段 5：提交推送

- 先 `git status`、`git diff`、`git log --oneline -5`。
- 只暂存本次相关文件：`docs/index.html`、`README.en.md`（若新增）。
- **确认 .gitignore 不排除 docs/ 和 README.en.md**（本项目只忽略 dist/build/logs/results/ucm_src 等）。
- 用中文简洁提交信息提交。
- 推送时若遇 `non-fast-forward`（本地落后远端），先 `git fetch`：
  ```bash
  GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10" git fetch origin main
  git rebase origin/main
  ```
  再推送：
  ```bash
  GIT_SSH_COMMAND="ssh -o BatchMode=yes -o ConnectTimeout=10" git push origin main
  ```

## 阶段 6：启用/校验 GitHub Pages

### 关于无法命令行自动开启

- 本仓库用 SSH（`git@github.com`）身份验证，未配置 token，也未安装 `gh` CLI。
- GitHub Pages 的**配置接口只能用 REST API / `gh`**，SSH 不行 → **无法从命令行直接开启 Pages**。
- 需用户手动在网页上完成以下 4 步：
  1. `https://github.com/<owner>/<repo>/settings/pages`
  2. Build and deployment → Source 选 **Deploy from a branch**
  3. Branch 选 `main`，目录选 **`/docs`**
  4. Save

### 校验

- 首次配置后需等 1~2 分钟才部署完成，期间访问可能返回 **404**，属正常。
- 用 webfetch 校验站点：`https://<owner>.github.io/<repo>/`
  - 404 → 未部署完，稍后重试；或检查 Actions 是否报错、分支名是否 `main`、首页是否 `index.html`。
- 部署成功后确认中英文都能加载并切换。

## 关键约定（务必遵守）

- 文档翻译不要写进 `i18n.py`；那是 GUI 界面翻译，与文档网页无关。
- `docs/index.html` 必须是首页文件名 `index.html`，否则 GitHub Pages 默认找不到站点。
- 用 SSH 时务必加 `GIT_SSH_COMMAND` 环境变量 + `BatchMode`，否则 git 可能卡在交互式连接（本项目实测坑点）。
- 不提交机密；只提交本次相关文件。
- 只有用户明确要求时才提交/推送/开启 Pages；开启 Pages 无 token 时引导用户手动完成。

## 收尾

- 更新 todo：将完成的阶段标记为 completed。
- 向用户汇报：新增/改动的文档文件、站点地址、是否需要用户手动开启 Pages。
