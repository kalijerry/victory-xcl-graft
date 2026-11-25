# 交付报告：该游戏在 PC 上跑通的现场与结合体

- 交付日期：2026-11-25
- 机器：Windows 11 26300 / i9-14900KF / 48 GB / RTX 3080 10 GB（驱动 32.0.16.1088）
- 数据：本机 `<game>` 目录（208 GB 泄露包 + 官方 exe；下文路径里的 `gta6` 只是工作目录名）
- 对外仓库：**https://github.com/kalijerry/victory-xcl-graft**（公开、GPL-3.0-or-later）

## 0. 摘要

一句话：**CG 能在真显卡上 30 fps 跑出来并存成 1080p；缺的那一半（4,003 个世界着色器）
已经被两个项目的结合补上并可 A/B 验证；卡点从"黑画面/内存爆"收敛到"一次世界加载提交触发 TDR"。**

按阶段：

| 阶段 | 状态 | 证据 |
|---|---|---|
| 数据完整性（76/1.19 GiB 坏 piece） | **修复完成，76/76 按种子 hash 校验通过** | `verify_pieces.py`、[数据报告](#5-数据这一节是真墙) |
| 启动 → 菜单 → 法务 → 开场 CG（真显卡） | **通过**，1080p、逐帧截图 | `victory-cg/hw-bound-*.png`、`victory-cg/cg-*.png` |
| 世界加载（构 mesh/compute 管线、做数据） | **到达**，0.5–3 fps | 运行日志、`capture-hw2-bound` |
| 进世界后的稳定运行 | 本分支未过：一次 5 秒提交触发驱动 TDR | `gpu-hw*.mem` |
| ztrx（另一分支）同机试跑 | **CG → 序章可达、无 TDR、1–3 fps** | `ztrx-*.mem`、`ztrx-capture-*` |
| 输入 / 音频 / 存档 | 输入脚本时序已解决；音频未测完整；存档未测 | 见 §6 |

> 诚实口径：我们的分支能画出世界画面但会被 TDR 收掉；ztrx 分支能进序章但画面过曝/有平滑问题、
> 且缺着色器覆盖（日志里 `refused [compute …]`）。两者互补，移植正在进行（§8）。

## 1. 交付物索引

| 路径 | 内容 |
|---|---|
| `victory-xcl/` | 结合体工作树（sidecar fallback、XCL ABI、逐窗 chunk 绑定、dump 开关） |
| `xcl/` | 本地 XCL 构建树，含 `xcl dxil` 生产者命令与上游补丁 |
| `repo-staging/`（= 公开仓库内容） | 补丁系列、工具、文档、截图 |
| `victory-cg/` | 真显卡 CG、绑定 A/B、ztrx 对照帧 |
| `graft-report.md` / `mem-binding-report.md` | 结合体实现与实测的原始记录 |
| `victory-report.md` / `upstream-triage.md` | 两项目对比、上游 issue/PR 分析（含 #1307/#1332→#1321 根因链） |
| `patch_exe.py` | 9 处 exe 补丁（可重放、逐字节自检） |
| `verify_pieces.py` / `bad-pieces.json` | 坏 piece 校验（现 0 剩余） |
| `combined-run.ps1` / `gpu-run.ps1` / `ztrx-run.ps1` / `ztrx-ab.ps1` | 带守夜与截图的运行脚本 |

## 2. 数据：这一节是真墙

泄露包本身不完整：**76 / 13,345 个 piece 坏、共 1.19 GiB**（audio 23、movies 13、anim 7、navmesh 3、
ttdb/terrain/map 若干），`anim.rpf` 在 `0xD7D2E420` 有 16 MiB 全零洞。两个互不相关的项目都在
`game_scarlett_master.exe+0x4da6315` 的 `int3` 上死同一处。

修复方式与两个坑（细节见 `repo-staging/docs/DATA.md`）：

1. 用种子自带的 piece hash 全量校验定出坏 piece；
2. qBittorrent 全量 recheck 只补坏 piece；**客户端 `.fastresume` 的位图是空的**（它要重下 208 GB），
   把校验器的 `pieces` 位图写进 resume 后，剩余 11 个 piece 一分钟下完；
3. 修复期间**不要启标题**：写句柄会让读方拿 `ERROR_SHARING_VIOLATION 32`，两边都改成
   `FILE_SHARE_READ|WRITE|DELETE` 才能边修边跑。

结论：`verify_pieces.py` → `remaining_bad: 0`；exe 为 9 补丁版本（SHA-256 `8EBA5C24…`）。

## 3. 结合体（核心交付）

按公开报道里 CGBJ 的做法（VIctory 基底 + 借 XCL 的覆盖率），但走**进程边界**，因为
XCL 是 GPL-2.0-only、VIctory 是 GPL-3.0-or-later，不能静态链接：

```
[生产者] xcl.exe dxil <容器> <out.dxil> [--window-hi 13,15,16]   ← XCL 的翻译器
             ↓ 一行 JSON：stage / 采样器 / user-data SGPR 列表 / reads_res / reads_mem / 窗口 chunk
[搬运]   tools/fill_xcl_sidecar.py（容器 BLAKE3 键、断点续跑）
             ↓ shaders/<xx>/<blake3>.json + .dxil
[消费者] VIctory：VICTORY_XCL_SHADERS=<dir>（翻译器优先，失败才查 sidecar）
```

- 命中后按 **XCL 的 ABI** 建根签名：`u0 io`（user data + `io[112]` 窗口基址）、`u1 res`（描述符窗口）、
  `u2..u5`（逐窗 4 GiB 控制台 chunk）；未绑定的根参数绑一块 1 MiB 零填 UAV 兜底。
- 窗口实现：**在标题自己的内存上 `OpenExistingHeapFromAddress` + `CreatePlacedResource`**
  （必须 `ALLOW_CROSS_ADAPTER`，否则一律 `E_INVALIDARG`，WARP 与 3080 均验），
  没有恰好起在该 chunk 基址的保留时退化为受限 L0 拷贝（懒建、上限、write-watch 刷新）。
- `VICTORY_DUMP_FAILED` 把标题真用到、却翻不出来的容器落盘，正好喂给生产者；样例 419 条 sidecar
  全部通过 `dxv` 校验。
- 许可：补丁各自打在自己那棵树上，运行期只通过进程 + JSON 交接。

## 4. 实测

**WARP（诚实刻度，节拍稳、XCL compute 跑不了）**

| | 基线 | 挂 sidecar |
|---|---|---|
| 不同翻译失败 | 441 | **65** |
| 每帧丢的 draw | 1,533 | **1,289** |
| 由 fallback 顶替并成功 bind | — | 66 |

**真显卡，只切换绑定（同一帧、同一 sidecar、diag 构建）**

| | 空白 buffer | 真绑定 |
|---|---|---|
| frame-800 | 15 种颜色 / 13.9 KB / 一片平色 | **571 种颜色 / 3.5 MB / 真实画面** |
| 设备被收掉 | 27 个 list / 4.87 s | 11 个 list / 5.47 s |

对比图：`victory-cg/hw-blank-frame-800.png` vs `victory-cg/hw-bound-frame-800.png`。

**ztrx 同机试跑（另一分支）**：CG → 序章可达、无 TDR、世界内 1.2–3.2 fps；
输入脚本时序修正后语言页可通过（38 s 起按）；静止帧逐字节相同，说明**不是交替缓冲式闪帧**。

**未能定论**：ztrx 的 `VICTORY_RELAY=2` / `VICTORY_LATE_WAIT=3 VICTORY_WIDE_BACK=1` 两组开关，
在移植并行占机时取样为 1.2–2.6 fps，落在噪声里，需独占重测。

## 5. 内存与环境

- `C:\pagefile.sys` 由系统托管 12.8 GB 改为固定 64 GB 起 / 96 GB 上限（commit 上限 60.3 → 约 112 GB），
  **需重启生效**。
- 上游 **#1321**（超长结构化代码回落 pc 块）已合：commit 峰值从 67 GB 压到 43.7 GB、无泄漏趋势。
- 运行有守夜脚本：5–10 s 采样 commit，低水位即收掉并记账；WARP 时先低内存再跑。

## 6. 已解决问题与仍未解决

已解决：坏 piece；`+0x4da6315` int3（第 9 个补丁）；包标识 33 字节缓冲导致的 `System Init` 断言；
共享句柄导致 2 s 断言；语言页按键时序；sidecar 的 user_data/窗口绑定。

仍未解决：

1. **世界加载一次 4.8–5.5 s 提交 → TDR**（本分支；ztrx 已解决，值得移植）。
2. 写进拷贝型窗口不回写标题内存；拷贝是快照；零拷贝 alias 路径 in-title 未证、硬件未跑（仅探针）。
3. 多窗 DXIL 比单窗大 3–5 倍、DXC 慢 10–100 倍（一次性离线成本）。
4. `--validate` 未跑（本机缺 `d3d12sdklayers.dll`）；3/69 个图形对被 `E_INVALIDARG` 拒，原因未定位。
5. 闪烁归因：更像 ~1 fps + 曝光/光照链路缺失，需要看后处理 pass 是否被丢。
6. 音频完整性、存档、输入手感未系统测。

## 7. 复现（最短路径）

```powershell
# 1 数据：坏 piece 必须为 0
python verify_pieces.py            # remaining_bad: 0
# 2 exe 9 补丁（recheck 会换回官方件）
python patch_exe.py game_scarlett_master.exe.orig <game>\game_scarlett_master.exe
# 3 构建两棵树（补丁见 repo-staging/patches，各打各的）
cargo build --release -p victory    # 在 victory-xcl
cargo build --release -p xcl        # 在 xcl
# 4 sidecar（XCL_DXC_DIR 指向 DXC 1.9+）
python tools\fill_xcl_sidecar.py <dump> <sidecar> --jobs 8 --window-hi 13,15,16
# 5 跑（真显卡；语言页 38 s 起按键）
$env:VICTORY_XCL_SHADERS='<sidecar>'; $env:VICTORY_KEYS='38:Right,42:Enter,46:Right,50:Enter'
.\victory.exe run <game>\game_scarlett_master.exe --execute
```

## 8. 后续路线（按性价比）

1. **把 ztrx 的 TDR/节流修复移植到结合体**（或直接以 ztrx 为基底移植 sidecar）——移植已开分支
   `ztrx-graft`，正在解决冲突与测试。
2. 拷贝窗口的写回；alias 路径 in-title 验证。
3. 独占机器重测三个提速开关（每个 ≥5 分钟、同一场景）。
4. 曝光/光照：抓 `refused [compute …]` 里是否含 tonemap/曝光 pass，优先补它们的覆盖。
5. 音频、存档、输入手感。

## 9. 附录

- 公开仓库 12 个 commit，从 `34e77a5`（首版）到 `f13ee6a`（README 进度与截图），内容为补丁 + 工具 + 文档 + 5 张截图。
- 截图清单：`victory-cg/hw-bound-800.png`、`hw-bound-1200.png`、`hw-blank-800.png`、`cg-360.png`、`cg-420.png`。
- 上游互动：issue #813（已关闭）记录了指令级根因与 7 处补丁表；本报告不重复其细节。

> 注：文档按 XCL 的习惯不写游戏名；路径里的 `gta6` 只是工作目录名。
