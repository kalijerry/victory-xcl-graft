# VIctory ⇄ XCL 桥（victory-xcl-graft）

English: [README.en.md](README.en.md)

把 [VIctory](https://github.com/Marvisak/VIctory) 缺的那一半——[XCL](https://github.com/ivall/xcl)
100% 覆盖的 RDNA2→DXIL 翻译——接进 VIctory，让世界着色器不再被丢掉。VIctory 当基底，
XCL 只当**翻译器进程**：两份 GPL 不兼容（VIctory GPL-3.0-or-later，XCL GPL-2.0-only），
所以桥走在进程边界上，靠一个 sidecar 目录和一行 JSON 交接，不静态链接。

> 现状（2026-11-24）：**能跑通、能验证，但还不是正确画面。**
> 真显卡 RTX 3080 上：不同翻译失败 424 → **45**、fallback 顶替 120 个 shader、
> 每帧 draw 815 → 1,929；但 XCL 的 DXIL 比 VIctory 自己的大 10–100 倍，
> PSO 创建把约 320 条排进队列，每帧"丢"的反而 561 → 920。
> WARP 是诚实刻度（节拍稳、XCL 的 compute 跑不了）：失败 441 → 65、每帧丢 1,533 → 1,289。
> 细节与它意味着什么：[docs/MEASUREMENTS.md](docs/MEASUREMENTS.md)。

## 为什么不是"把两个项目合了"

* 公开报道里的 CGBJ（私有）就是"VIctory 基底 + 借 XCL 的工作"这么进游戏的，代码没公开；
* VIctory 社区正用**自己的 PR** 追同一批 4,003 个失败（`#953` +230、`#305`/`#539` +520 个程序），
  但没人做跨项目桥；
* 于是这里走反方向：**不移植规则，直接借翻译结果**，把两边的强项拼起来。

## 怎么工作

```
[生产者]  xcl.exe dxil <容器> <out.dxil>        ← XCL 的翻译器（patches/xcl）
              ↓ 一行 JSON：stage + 需要的 static sampler
[搬运]    tools/fill_xcl_sidecar.py             ← 对失败容器算 BLAKE3，写 sidecar，断点续跑
              ↓ shaders/<xx>/<blake3>.json + .dxil
[消费者]  VIctory: VICTORY_XCL_SHADERS=<dir>    ← 翻译器优先，失败才查 sidecar（patches/victory）
```

* 命中后按 **XCL 的 ABI** 建根签名（root UAV `u0..u5` space 0、采样器 space 1），draw 不再丢；
* `VICTORY_DUMP_FAILED=<dir>` 把标题真的用到的、翻不出来的容器落盘，正好喂给生产者；
* sidecar 全空时行为与上游完全一致（翻译器永远先跑）。

## 快速上手

```powershell
# 1. 打补丁（两棵树各自打）
git clone https://github.com/Marvisak/VIctory; cd VIctory
git apply ../patches/victory/0001-xcl-sidecar-fallback.patch
git apply ../patches/victory/0002-cargo-lock.patch
cargo build --release -p victory

git clone https://github.com/ivall/xcl; cd ../xcl
git apply ../patches/xcl/0001-dxil-producer-command.patch      # 及 0002..0006，见下
cargo build --release -p xcl

# 2. 跑一次标题，让失败容器落盘
$env:VICTORY_DUMP_FAILED='...\failed'; $env:VICTORY_D3D12_WARP='1'
.\victory.exe run <exe> --execute

# 3. 生成 sidecar（XCL_DXC_DIR 指向 DXC 1.9+）
$env:XCL_DXC_DIR='...\dxc\bin\x64'
python tools\fill_xcl_sidecar.py ...\failed ...\sidecar

# 4. 带着 sidecar 再跑
$env:VICTORY_XCL_SHADERS='...\sidecar'
```

## 补丁清单（`patches/xcl`）

| 补丁 | 作用 | 是否必需 |
|---|---|---|
| 0001 | `xcl dxil` 生产者命令（VS/PS/CS，32-lane 走 split） | 必需 |
| 0002 | 包标识按 33 字节缓冲返回（标题在 `System Init` 就断言） | 必需 |
| 0003 | 读方允许写方（`FILE_SHARE_READ\|WRITE\|DELETE`），修复期间也能跑 | 强烈建议 |
| 0004 | 上游 **#1321**：超长结构化代码回落 pc 块（commit 以 1 GB/s 涨到 115 GB 的根因） | 强烈建议 |
| 0005 | 上游 **#1273**：bind 不等卡在队列后面的构建 | 建议 |
| 0006 | 预加载路径的 `build_is_wanted` 漂移修正 | 建议 |

`0002` 同时含 13 行 `[api]` 调试日志（warn 级），可自行删。

## 还缺什么（按优先级）

1. **绑定面**：sidecar 已带 `user_data`（读到的 dword 序号）与 `reads_res`/`reads_mem`，但 `slot`/`kind` 与 `u1/u2..u5` 的实际绑定还没接；`user_data`、`u1 res` / `u2..u5 mem` 全空 → 现在只保证
   "不丢、能 bind"，初值 SGPR 和地址读回 0，画面缺元素。需要 XCL 翻译时把"读了哪些
   user-data dword、地址从哪个 u 寄存器来、对应哪个根参数"报出来。
2. **大 DXIL 的编译积压**：XCL 的 DXIL 10–100 倍大，要做 sidecar 管线的离线预编译
   （XCL 的 `pipelines` + 驱动 blob 缓存那套已验证可复用）并给 worker 限并发。
3. **MS/GS 容器**（746 个失败）要两趟管线，`xcl dxil` 还不支持。
4. 世界加载一次 4.8 s 提交触发驱动 TDR。

## 数据前提（重要）

该游戏（最新发售的那个 Xbox 标题，下面只叫「该游戏」，不写名字）的包本身不完整：**76/13,345 个 piece 坏、1.19 GiB**，`anim.rpf` 有 16 MiB 全零洞，
两个项目都会在 `+0x4da6315` 撞同一个 `int3`。修复方法、`fastresume` 位图坑、
共享句柄坑见 [docs/DATA.md](docs/DATA.md)。

## 许可

桥的胶水：GPL-3.0-or-later（同 VIctory）。文中不写该游戏的名字，路径里的 `gta6` 只是作者的工作目录名。`patches/xcl` 打到 GPL-2.0-only 的 XCL 上，
各自保持自己的许可；两者只在运行期通过进程 + JSON 交接。仓库不含任何游戏数据。
