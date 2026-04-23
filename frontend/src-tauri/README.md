# 必赢通 桌面版 (Tauri)

Rust + Tauri 封装必赢通前端 + Flask 后端成单体桌面应用。

## 开发环境准备

需要 Rust 工具链（一次性）：

```
winget install Rustlang.Rustup
rustup default stable
```

## 开发模式

两个终端分开跑：

```
# Terminal 1 - Flask 后端
cd biyingtong
python app.py

# Terminal 2 - Tauri + Vite
cd biyingtong/frontend
npm run tauri dev
```

Tauri 在 dev 模式下**不会自动拉起** Flask（需要你手动启动），因为 Flask 的启动日志
比较多，混在 Tauri 日志里太乱。release 模式（`npm run tauri build`）会自动
spawn `python app.py` 作为 sidecar。

## 打包发布

```
cd biyingtong/frontend
npm run tauri build
```

产物在 `src-tauri/target/release/bundle/` 下：
- Windows: `.msi` 安装包 + `.exe` portable
- macOS: `.dmg`
- Linux: `.deb` / `.AppImage`

Windows 打包的 app 需要目标机器预装 Python 3.10+，Flask 依赖通过 `pip install -r requirements.txt` 自行安装。后续可以用 PyInstaller 把 Flask 打包成独立 exe
避免这个依赖。

## 图标

放在 `src-tauri/icons/`，规范文件：
- `32x32.png`
- `128x128.png`
- `128x128@2x.png`
- `icon.icns` (macOS)
- `icon.ico` (Windows)

生成命令：`npm run tauri icon <source.png>`（需要 1024×1024 PNG 源）。
