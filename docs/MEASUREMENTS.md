# 测量（RTX 3080 / 48 GB / i9-14900KF，2026-11-24）

一组同路线、同数据、同构建的成对运行（基线 vs 挂 sidecar），以及必须一起读的注释。

## 真显卡（RTX 3080 10 GB，1080p）

| | 基线 | 挂 sidecar |
|---|---|---|
| 被翻译器拒的 shader | 424 | **45** |
| 由 fallback 顶替 | — | 120 |
| 被拒 PSO（全是 compute 的 `WaveSize(64)`） | 115 | 99 |
| 每帧丢的 draw（15/28 次采样均值） | 561 | 920 |
| 每帧 draw | 815 | **1,929** |

**为什么"丢"反而变多**：XCL 的 DXIL 比 VIctory 自己的大 10–100 倍（就是 XCL 里那些
400 KB–1 MB 的巨型程序，它自己的跑法也这样），PSO 创建把约 320 条排进 `being made` 队列
（`pipeline/make.rs`：队列里的算丢），基线没有这个积压。**所以失败数不是唯一指标，
积压是下一仗。**

## WARP（节拍稳定，XCL 的 compute 跑不了：`WaveLaneCountMax=4`）

| | 基线 | 挂 331 条 sidecar |
|---|---|---|
| 不同失败 shader | 441 | **65** |
| 每帧丢的 draw | 1,533 | **1,289** |
| 每帧 draw | — | 上升 |

WARP 是这批改动唯一的诚实刻度：没有 GPU 编译积压干扰，失败与丢弃同时下降。
同样的 66 个 shader 在日志里带 `fallback=true` 并**成功 bind**，不再是 `host pipeline refused`。

## CG / 阶段（真显卡，30 fps 锁定）

启动 → 账号选择 → 语言 → 法务 → **开场 CG 实机播放**（240/256/300/360/420 帧为 2.8–4.2 MB
真实画面，UI 帧 6–51 KB）→ 世界加载 2,633 draw/帧 → **一次 4.8 s 的提交（23–28 个 list）后
`0x887A0006 DEVICE_HUNG`**，驱动重置（桌面 3840×2160 → 2560×1440，自行恢复）。
峰值私有内存 22.2 GB，剩余 commit 35 → 7.2 GB。WARP 更早还在
"VICE CITY, TWO YEARS AGO" 任务标题卡（2,781 draw/帧）之后才被软件设备收掉。

## 读出这些数字时的注意

* 两台机器/两个后端不可直接对比；WARP 的 draw 数不代表硬件路径。
* `--validate` 没有跑（本机没有 `d3d12sdklayers.dll`，`D3D12GetDebugInterface` 报
  `0x887A002D`），所以"能 bind"不等于"DXIL 被验证过"。
* XCL 的 `dxil` 目前按 1 个 UMA 窗口翻译；运行时窗口数多于 1 时 HLSL 会不同（缓存键含窗口数）。
* 3/69 个"原生 VS + sidecar PS"的图形对被 `E_INVALIDARG` 拒（签名已对上，原因未定位）。

## 绑定面（u0/u1/u2..）落地前后（WARP，同一 diag 构建、同一 sidecar）

| | 空白 buffer 基线 | 真实绑定 |
|---|---|---|
| 由 fallback 翻出 | 87 | 92 |
| `does not translate` | 51 | 45 |
| 被拒 PSO | 196 | 198 |
| frame-256 与基线的 8×8 亮度网格差 | — | **17.5/255** |
| frame-256 边缘能量 | 6.11 | 7.67 |
| frame-256 通道均值 | (89.0, 102.0, 26.2) | (90.5, 88.2, 47.1) |
| frame-128/512 差 | — | 1.6 / 1.7 级 |

两次都在 ~86 s 被软件设备收掉（WARP 上同一帧段的既有行为），无新的告警类别；
窗口只建了一次（chunk 0，935,526,400 B，走的是受限拷贝路径）。
帧：`capture-bound/frame-256.png` vs `capture-blank/frame-256.png`。

样例 sidecar 的全部 363 条 DXIL 都过了 `dxv` 校验（`gta6\cl-sidecar-win`）。
