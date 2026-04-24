# 必赢通桌面版发布流水线 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 打 git tag `v5.x.x` 时自动在 Windows runner 上构建 Tauri 桌面安装包（`.msi` + `.exe`），发布到 GitHub Releases，用户可直接下载安装。

**Architecture:** 单一 workflow 文件 `.github/workflows/release.yml`，tag 触发，Windows runner 一把梭：Node 20 + Rust stable 工具链装配 → `tauri-apps/tauri-action@v0` 负责 build + Release 创建 + asset 上传。不做 CI 测试流水线（用户明确要求）。

**Tech Stack:** GitHub Actions · windows-latest runner · Node 20 · Rust stable · Tauri 2 · `tauri-apps/tauri-action@v0` · `Swatinem/rust-cache@v2` · `dtolnay/rust-toolchain@stable`

---

## 前置事实

- Tauri 配置已完整：`frontend/src-tauri/tauri.conf.json` + `Cargo.toml` 版本都是 `5.0.0`
- `frontend/package.json` 版本是 `0.0.0`（不影响 `tauri-action` 构建，它读 `tauri.conf.json`；但对齐保险）
- Bundle targets `"all"` → Windows runner 上产出 `.msi`（WiX）+ `.exe`（NSIS）
- 仓库：`github.com/jixianyihao/biyingtong`，主分支 `main`
- 当前 worktree 分支：`worktree-mighty-shimmying-pie`（已 push，有上游）

## 作用域限定

**做**：push `v*.*.*` tag → Windows 桌面安装包 → GitHub Release 下载链接。

**不做**：
- CI 测试 workflow（用户明确排除）
- macOS / Linux 桌面包（项目因 TDX SDK 依赖 Windows-only）
- 代码签名（SmartScreen 警告暂时接受）
- 自动版本 bump 脚本 / changelog 自动化

## 关键决策

**选 `tauri-apps/tauri-action@v0` 而非手动 `npm run tauri build + upload-artifact + gh release create`**：

| 维度 | tauri-action | 手动 |
|---|---|---|
| workflow 行数 | ~35 | ~70 |
| 自动创建 Release | ✅ | 需 `gh release create` |
| 自动上传 `.msi` / `.exe` | ✅ | 需手写 glob |
| 版本号 `__VERSION__` 替换 | ✅ | 需手写 |
| 控制粒度 | 低 | 高 |

此处不需要高粒度控制，用 tauri-action。

## 文件变更总览

| 操作 | 路径 | 作用 |
|---|---|---|
| Modify | `frontend/package.json:4` | version `0.0.0` → `5.0.0`（三处对齐） |
| Create | `.github/workflows/release.yml` | tag → Tauri build → Release |

业务代码零改动。

---

### Task 1: 对齐 `frontend/package.json` 版本号

**Files:**
- Modify: `frontend/package.json:4`

- [ ] **Step 1: 查看当前 version**

Run:
```bash
grep '"version"' frontend/package.json
```

Expected:
```
  "version": "0.0.0",
```

- [ ] **Step 2: 改为 5.0.0**

编辑 `frontend/package.json:4`：

```json
  "version": "5.0.0",
```

- [ ] **Step 3: 验证三处一致**

Run:
```bash
grep '"version"' frontend/package.json
grep '^version' frontend/src-tauri/Cargo.toml
grep '"version"' frontend/src-tauri/tauri.conf.json
```

Expected: 三行输出都包含 `5.0.0`。

- [ ] **Step 4: Commit**

```bash
git add frontend/package.json
git commit -m "chore: align frontend package.json version to 5.0.0"
```

---

### Task 2: 创建 release workflow

**Files:**
- Create: `.github/workflows/release.yml`

- [ ] **Step 1: 确认目录不存在（首次）**

Run:
```bash
ls .github/workflows 2>&1 || echo "not-exists-ok"
```

Expected: `not-exists-ok` 或空目录。

- [ ] **Step 2: 写入 workflow 文件**

创建 `.github/workflows/release.yml`：

```yaml
name: release

on:
  push:
    tags: ['v*.*.*']
  workflow_dispatch:
    inputs:
      tag:
        description: '调试用：手动指定 tag 名（正常走 tag push）'
        required: true
        default: 'v5.0.0-dryrun'

jobs:
  build-desktop:
    runs-on: windows-latest
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Setup Node 20
        uses: actions/setup-node@v4
        with:
          node-version: '20'
          cache: 'npm'
          cache-dependency-path: frontend/package-lock.json

      - name: Setup Rust stable
        uses: dtolnay/rust-toolchain@stable

      - name: Cache Rust build artifacts
        uses: Swatinem/rust-cache@v2
        with:
          workspaces: frontend/src-tauri -> target

      - name: Install frontend deps
        working-directory: frontend
        run: npm ci

      - name: Build Tauri bundle + create Release + upload assets
        uses: tauri-apps/tauri-action@v0
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
        with:
          projectPath: frontend
          tagName: ${{ github.event_name == 'workflow_dispatch' && inputs.tag || github.ref_name }}
          releaseName: '必赢通 __VERSION__'
          releaseBody: |
            必赢通桌面版 Windows 安装包。

            - 下载 `.msi` 双击安装（推荐）
            - 或下载 `.exe` 便携版

            首次启动 Windows SmartScreen 可能警告"未知发布者"，点"更多信息 → 仍要运行"即可。
          releaseDraft: false
          prerelease: false
```

- [ ] **Step 3: Lint YAML（轻量）**

Run:
```bash
python -c "import yaml; yaml.safe_load(open('.github/workflows/release.yml'))" && echo "yaml-ok"
```

Expected: `yaml-ok`（无异常即通过）。

- [ ] **Step 4: Commit**

```bash
git add .github/workflows/release.yml
git commit -m "ci: add Tauri Windows release workflow triggered by v*.*.* tag"
```

---

### Task 3: 推送并在 GitHub 验证 workflow 可见

**Files:** N/A（推送 + UI 验证）

- [ ] **Step 1: Push 当前分支**

```bash
git push
```

- [ ] **Step 2: UI 验证 workflow 出现**

访问 https://github.com/jixianyihao/biyingtong/actions

Expected: 左栏 "All workflows" 下新增 `release` 条目（当前无 run，因为还没打 tag）。

---

### Task 4: 配置仓库 Workflow 权限

**Files:** N/A（GitHub repo settings UI 操作）

说明：`tauri-action` 需要 write 权限创建 Release + 上传 assets。仓库创建时默认 `GITHUB_TOKEN` 只有 read 权限，必须手动放开。

- [ ] **Step 1: 打开设置**

访问 https://github.com/jixianyihao/biyingtong/settings/actions

- [ ] **Step 2: Workflow permissions 放开**

在 "Workflow permissions" 段：
- 选中 "Read and write permissions"
- 勾选 "Allow GitHub Actions to create and approve pull requests"
- 点击 "Save"

- [ ] **Step 3: 截屏或记录已改**

截图保存（可选，便于后续查验）。

---

### Task 5: 冒烟发版 —— 打 tag 跑通全链路

**Files:** N/A（git tag + push）

- [ ] **Step 1: 确认 worktree 干净**

Run:
```bash
git status
```

Expected: `nothing to commit, working tree clean`。

- [ ] **Step 2: 打 annotated tag**

```bash
git tag v5.0.0 -m "release: initial desktop build"
```

- [ ] **Step 3: 推送 tag**

```bash
git push origin v5.0.0
```

- [ ] **Step 4: 监视 Actions 运行**

访问 https://github.com/jixianyihao/biyingtong/actions

找到刚触发的 `release` run（tag 名为 `v5.0.0`），点进去看 `build-desktop` job 日志。

预计时间线（冷缓存）：

| 阶段 | 时间 |
|---|---|
| Checkout + setup node | ~30s |
| `npm ci` | ~1-2 min |
| Rust toolchain install | ~1-2 min |
| `cargo build --release`（首次） | ~10-15 min |
| Bundle MSI + NSIS | ~1 min |
| Create Release + upload | ~30s |
| **合计** | **~15-20 min** |

Expected: 全部步骤绿灯 ✅。

- [ ] **Step 5: 验证 Release 条目**

访问 https://github.com/jixianyihao/biyingtong/releases

Expected:
- 条目标题：`必赢通 5.0.0`
- Assets 至少包含：
  - `必赢通_5.0.0_x64_zh-CN.msi`（或 `_en-US.msi`）
  - `必赢通_5.0.0_x64-setup.exe`

- [ ] **Step 6: 下载安装冒烟**

- 在 Windows 机器下载 `.msi`
- 双击安装（SmartScreen → "更多信息" → "仍要运行"）
- 从开始菜单启动"必赢通"
- Expected：窗口弹出，显示前端界面（若后端未启动则提示"无法连接"——正常，后端 Flask + TDX 是另一条链路，不在本 plan 范围）
- 关闭窗口

- [ ] **Step 7: 若失败：排错表 + 清理坏 tag**

| 症状 | 原因 | 修复 |
|---|---|---|
| `Resource not accessible by integration` | Workflow permissions 没设 write | 回 Task 4 重配 |
| `cargo` MSVC 链接错误 | windows-latest 工具链问题（罕见） | 重跑 workflow |
| `npm ci` lock 不匹配 | package.json 改了但 lock 没更新 | 本地 `cd frontend && npm install` 后 commit `package-lock.json` |
| Release 创建但无 assets | `projectPath` 没对上 | 检查 workflow 里 `projectPath: frontend` |
| `Error: Input required and not supplied: tagName` | `github.ref_name` 在 workflow_dispatch 下为空 | 已在 plan 用三元处理，不应发生 |

修复后删除坏 tag + 重推：

```bash
git push --delete origin v5.0.0
git tag -d v5.0.0
# 修完后
git tag v5.0.0 -m "release: initial desktop build"
git push origin v5.0.0
```

---

## Verification（合并验证）

完整走完 Task 5 即 end-to-end 验证通过：

- ✅ `.github/workflows/release.yml` 在 GitHub Actions 可见
- ✅ `git push origin v5.0.0` 后触发 workflow
- ✅ Windows runner 成功 build Tauri bundle
- ✅ GitHub Release `必赢通 5.0.0` 自动创建，含 `.msi` + `.exe` 两个 asset
- ✅ `.msi` 在 Windows 能装，"必赢通"窗口启动

## Self-Review

**Spec coverage**：用户要求"可以发布版本的桌面版本"。Task 2 的 workflow 定义 + Task 5 的冒烟发版覆盖此需求。无遗漏。

**Placeholder scan**：每个 Step 都有具体命令或代码块，无 TBD / TODO / "implement later" / "add error handling" 等空洞描述。

**Type consistency**：
- action 版本在 workflow 内一致（`@v4` / `@v0` / `@stable` / `@v2`）
- 路径统一（`frontend/` + `frontend/src-tauri/`）
- 版本号三处统一为 `5.0.0`
- tag 命名约定 `v*.*.*` 贯穿 workflow trigger + Task 5 示例

**边界条件**：`github.ref_name` 在 `workflow_dispatch` 下为分支名而非 tag 名，已用三元 `github.event_name == 'workflow_dispatch' && inputs.tag || github.ref_name` 兼容。

## 后续可迭代（本次不做）

- `scripts/bump-version.sh` —— 三处版本一把改
- Windows code signing —— 消除 SmartScreen 警告
- README 顶部加"最新版本下载"徽章 + 链接
- PyInstaller 把后端打进安装包，减少用户配置步骤
- macOS / Linux 包（若未来 TDX 有替代方案）
