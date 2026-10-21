# PetalMenu 花瓣菜单

Windows 上的 PyQt6 放射状「花瓣」菜单：在资源管理器里选中若干文件，按热键弹出花瓣，
每个花瓣绑定一个打开方式，点一下就启动（例如 PotPlayer 播放视频、默认程序打开图片、打开所在文件夹）。

## 功能

- 全局热键唤起花瓣菜单（当前默认 `alt+z`），在鼠标位置绘制，Esc / 点外部自动关闭
- 花瓣按扩展名过滤：视频选中时只显示视频类打开方式，图片同理
- 六类文件开箱可用：视频、图片、文档、音频、压缩包、光盘镜像。扩展名表就是配置文件里的
  `video_exts` / `document_exts` 等，想加类型直接往里塞扩展名
- 每类可以配一个「直开」热键（`programs.<类别>` 指定的程序）；`open_auto` 会自动判断类型再选程序，
  认不出的类型交给系统默认打开
- 左键点花瓣中心 → 在资源管理器里打开文件所在目录（同时选中该文件）
- 自绘放射状菜单，带展开动画、五套配色方案、四档花瓣大小
- 托盘图标右键 → 设置菜单：呼出快捷键 / 配色方案 / 花瓣大小，全部即时生效并写回配置
- 花瓣从左（9 点钟）起顺时针排列；第一片固定是「默认打开」，走系统默认程序
- 第二片起显示程序名：优先系统注册名，其次 exe 版本信息，最后退回可执行文件名
- 没配程序的花瓣留白（不写文字），点它只关掉菜单
- 右键中心花瓣 → 设置花瓣数量（`0` = 显示全部匹配项；`N` = 取前 N 个）
- 已配置的打开方式不足 N 个时自动补「未配置」占位花瓣（灰底虚线），右键占位花瓣即可现场绑定程序并写回配置
- 托盘常驻：右键只有三项设置 + 「退出」，热键改完立刻热更新，不用重启
- 配置持久化在 `%APPDATA%\PetalMenu\config.yaml`，首次启动自动生成，可从 exe 同级目录迁移旧配置

## 托盘右键设置

右键任务栏图标：

```
呼出花瓣菜单的快捷键 ▸  alt+z / ctrl+alt+z / ctrl+shift+z / alt+q / alt+w / ctrl+alt+j / 自定义…
配色方案 ▸              经典 / 中式 / 和式 / 莫兰迪 / 清新
花瓣大小 ▸              小 78% / 标准 100% / 大 126% / 特大 155%
───────────────────────
退出
```

- 快捷键列表里被别的程序占用的组合会标「（被占用）」并置灰，选中即时重注册；
  想用自己的组合就点「自定义…」手输（如 `ctrl+alt+z`、`f9`）
- 配色和大小改完立刻重画菜单并写回 `config.yaml`，托盘图标颜色也会跟着换
- 设置只作用于「呼出花瓣菜单」这一个热键；`open_*` 那组直开热键仍在 `config.yaml` 里配

## 选择来源

| 来源 | 判定方式 |
| --- | --- |
| Windows 资源管理器 | 前台窗口类名 `CabinetWClass`，读当前目录 + 选中项 |
| Everything | 前台窗口类名 `EVERYTHING`，读结果列表选中项 + 当前目录 |

## 文件结构

```
main.py          入口：热键、托盘、配置读写、来源检测、启动目标程序
hotkey_hook.py   Win32 低级键盘钩子（WH_KEYBOARD_LL）实现的全局热键
petal_menu.py    自绘花瓣菜单、编辑花瓣对话框、设置数量对话框
PetalMenu.spec   PyInstaller 打包配置
config.yaml       默认配置模板
tests/           验证脚本（配置、UI、热键吞键、Everything 支持、打包检查等）
```

## 运行 / 打包

```bat
pip install PyQt6 PyYAML
python main.py

pyinstaller PetalMenu.spec --noconfirm --clean --distpath dist_vN --workpath build_vN
```

## 配置示例

```yaml
hotkeys:
  show_menu: alt+z
  open_video: "ctrl+alt+v"
  open_image: "ctrl+alt+p"
  open_document: ""        # 留空 = 这一类不注册直开热键
  open_audio: ""
  open_archive: ""
  open_disc: ""
  open_auto: "ctrl+alt+o"  # 自动识别类型后直开

# 六类文件的扩展名表；不写或写空会自动补默认值
video_exts: [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".ts", ".webm"]
image_exts: [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".tif", ".tiff"]
document_exts: [".pdf", ".doc", ".docx", ".xls", ".xlsx", ".ppt", ".pptx", ".epub", ".txt", ".md"]
audio_exts: [".mp3", ".flac", ".wav", ".aac", ".m4a", ".ogg", ".opus", ".wma", ".ape"]
archive_exts: [".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz", ".zst", ".cab"]
disc_exts: [".iso", ".img", ".bin", ".cue", ".nrg", ".mdf", ".mds", ".vhd", ".vhdx"]

programs:                  # 各类别的「直开」程序，空 = 系统默认
  video: ''
  image: ''
  document: ''
  audio: ''
  archive: ''              # 例如 'C:\Program Files\7-Zip\7zFM.exe'
  disc: ''

palette: classic        # 配色：classic 经典 / chinese 中式 / japanese 和式 / morandi 莫兰迪 / fresh 清新
petal_size: normal      # 花瓣大小：small 78% / normal 100% / large 126% / xlarge 155%

petal_count: 4          # 总片数（含固定的第一片）；0 = 全部；N = 前 N 个（不足补占位花瓣）

# 花瓣顺序：第一片永远是「默认打开」（系统默认程序），第二片起按下面 petals 的顺序
# 从左（9 点钟）开始顺时针排。显示名只由 program 决定：
#   系统注册名（HKCR\Applications\<exe>\FriendlyAppName）> exe 版本信息（文件说明/产品名）> 可执行文件名
# name 字段现在只是给你自己看的备注；program 留空的花瓣显示为空白，点它只关菜单。
petals:
  - name: "PotPlayer"
    program: 'C:\Program Files\DAUM\PotPlayer\PotPlayerMini64.exe'
    exts: [".mp4", ".mkv", ".avi", ".mov", ".flv", ".wmv", ".m4v", ".ts", ".webm"]
  - name: "所在文件夹"
    program: "__explorer__"   # 特殊值：打开目标所在目录
```

## 为什么不用 `keyboard` 库

`keyboard==0.13.5` 的 `_winkeyboard.py` 里有一段「忽略重复 Alt」的启发式：

```python
fake_alt = (LLKHF_INJECTED | 0x20)          # 0x30
if vk != VK_PACKET and flags & fake_alt != fake_alt:
    process_key(...)
```

事件的 `flags` 同时带 `injected(0x10)` 和 `context(0x20)` 时会被整条丢弃。
而 ToDesk / RDP / 虚拟键盘 / SendInput 注入按键时恰好会带上这两位，于是所有含 `Alt`
的组合键在远程会话里完全失效（普通字母 `flags=0x10` 反而正常，很容易误判成「虚拟键盘没发键」）。

本项目直接读原始钩子事件，只忽略 `VK_PACKET`（Unicode 文本注入）和 0.3s 内的自动重复，
修饰键状态用 `GetAsyncKeyState` 取，因此物理键盘、远程键盘、软键盘、AHK 发送都能触发。

命中热键后会把主键吞掉（钩子返回非 0），否则前台窗口会对「没有菜单助记符的 Alt+字母」
放一声系统提示音，且字母会被敲进目标程序。修饰键的 keyup 必须放行，避免前台窗口卡在菜单模式。
`PETALMENU_SWALLOW=0` 可关掉吞键做对照。

## 调试

- `PETALMENU_HOOK_DEBUG=1` → 每个键盘事件与命中写 `%APPDATA%\PetalMenu\hook.log`
- `%APPDATA%\PetalMenu\debug.log` → 每次配置 load/save 与花瓣编辑结果

## 已知限制

- 仅 Windows（依赖 Win32 钩子、`CabinetWClass` / Everything 窗口探测）
- `alt+x`、`ctrl+alt+p`、`win+b` 等组合在部分机器上已被占用或与系统行为冲突，换热键前先确认空闲
  （`tests/_hkfree.py` 会逐个试 `RegisterHotKey`，直接报出哪个被占用）
- 配置里留空的直开热键不会被注册，也不会出现在任何菜单里——要用就先在 `config.yaml` 的
  `hotkeys.open_<类别>` 填一个组合键（托盘菜单只管「呼出花瓣菜单」这一个热键）
- Everything 模式下若索引过期，拼出的完整路径会指向旧文件名，需要重建 Everything 索引
