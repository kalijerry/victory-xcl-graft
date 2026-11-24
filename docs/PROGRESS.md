# 进度（随时更新）

对外追踪器 [PortWatch VI](https://portwatch-vi.xyz/) 把这条线放在 **67%** 一档
（2026-11-24 19:5x；榜首 CGBJ 72%，私有、已进游戏）。这里记的是支撑那个数字的**实际证据**，
以及它换来的取舍——不是靠截图里的气氛。

## 阶梯

| 阶段 | 状态 | 证据 |
|---|---|---|
| 构建、`victory config`、preflight | 通过 | `patch_exe.py`、构建日志 |
| 启动 → 账号 → 语言 → 法务 | 通过，30 fps 锁定 | `docs/screens/hw-bound-800.png` |
| 开场 CG（真显卡、1080p） | **通过**，逐帧截下 | `docs/screens/cg-360.png`、`cg-420.png` |
| 世界加载（做数据、构 mesh/compute pipeline） | **到达**，0.9–2 fps | 运行日志、`docs/screens/hw-bound-1200.png` |
| 进世界后的稳定运行 | 未过：一次世界加载提交触发驱动 TDR（`0x887A0006`） | `gpu-hw*.mem` |
| 输入 / 音频 / 存档 | 未测 | — |

## 两个项目结合带来的部分（可 A/B）

同一帧、同一 sidecar、同一 diag 构建，只切换绑定：

| | 空白 buffer | 真绑定 |
|---|---|---|
| frame-800 | 15 种颜色、13.9 KB、一片平色 | **571 种颜色、3.5 MB、真实画面** |
| `does not translate`（WARP 同路线） | 441 | 65 |

左：`docs/screens/hw-blank-800.png`，右：`docs/screens/hw-bound-800.png`。

## 数据前提

泄露包本身不完整（76/13,345 个 piece 坏、1.19 GiB），`anim.rpf` 有 16 MiB 全零洞；
两个项目会在同一条 `int3` 上死。全部已按种子 piece hash 修复并校验通过，
过程见 [DATA.md](DATA.md)——**不修数据，下面任何一行都跑不出来**。

## 还没做

1. 世界加载那次 4.8–5.5 s 的提交 → TDR（切开提交 / 限并发 compute，`VICTORY_D3D12_DEBUG=1` 抓命令）。
2. 写进拷贝窗口不回写标题内存；拷贝是快照；零拷贝 alias 路径 in-title 未证。
3. 多窗 DXIL 比单窗大 3–5 倍、DXC 慢 10–100 倍（一次性离线成本，已用整包预翻摊销）。
4. 输入、音频完整性、存档。

## 说明

* 截图是运行输出，不含游戏数据文件；分辨率已从 1920 缩到 1280。
* 数字都来自本机（i9-14900KF / 48 GB / RTX 3080 10 GB），WARP 与真显卡分开标注，不混用。
