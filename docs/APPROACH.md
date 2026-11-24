# 接法（给改代码的人）

## 为什么走进程边界

VIctory 是 GPL-3.0-or-later，XCL 是 GPL-2.0-only；GPL-3 的代码不能直接塞进 GPL-2-only 的树。
所以不做库级移植，而是：**XCL 出一个单容器翻译命令，VIctory 读它写出来的文件**。
两边各自的许可都不动，JSON 是唯一契约。

## 消费者一侧（`patches/victory/0001`）

接缝只有一个，且很窄：

* `crates/victory-gpu/src/pipeline.rs` 的 `Shader::translated()` 已经把翻译结果存在
  `OnceLock<Option<Translated>>` 里，失败时打一条
  `shader does not translate; its pipelines' draws are dropped`。
* fallback 只在**这条错误路径之后**才被查，翻译器永远先跑；`VICTORY_XCL_SHADERS` 未设时行为与上游一致。
* `Translated { host: HostShader, used }` 由 sidecar 构造；DXIL 必须是带 `DXIL` part 的 DXBC 容器，
  否则用文件名报错。

契约（`xcl.rs` 模块文档里有同一份）：

```json
{
  "stage": "vs" | "ps" | "cs" | "ms",
  "dxil_file": "<相对于 sidecar 目录，或绝对路径>",
  "user_data": [{ "index": 4, "slot": 2, "kind": "constants" | "table" }],
  "samplers": [[146, 12582912, 407896064, 0, 0]],
  "root_cbvs": [3],
  "root_srvs": [7]
}
```

除 `stage`/`dxil_file` 外都可缺省或为空。`samplers` 是 console 采样器描述字，XCL 会在末尾多给
一个比较位（0/1），接受并忽略。

### ABI

XCL 的 DXIL 用 XCL 自己的 ABI：root UAV `u0..u5` 在 space 0、静态采样器在 space 1。
`HostShader.xcl` 标记它，根签名与 draw 路径都按这个 ABI 走；`u0..u5` 里 sidecar 没填的，
一律绑一块 1 MiB 零填 upload buffer（读回 0，不 fault）。

### 开关

| 环境变量 | 作用 |
|---|---|
| `VICTORY_XCL_SHADERS=<dir>` | 打开 fallback（未设＝关） |
| `VICTORY_DUMP_FAILED=<dir>` | 把翻译失败的容器按 `<blake3>.bin` 落盘，喂给生产者 |
| `VICTORY_XCL_FORCE=<16 位 hex,[…]>` | 即使原生翻译成功也用 sidecar（只用于对比验证） |

## 生产者一侧（`patches/xcl/0001`）

`xcl dxil <容器> <out.dxil>`：解析 XDBC/FSSM 容器、按硬件变体定 stage（4/5/6 → VS/PS/CS）、
调 XCL 自己的 `console_to_dxil_for(..., split_wave64=true)`（本机 `WaveLaneCountMax` 是 32，
wave64 compute 必须走 split 形式，否则 D3D12 以 `E_INVALIDARG` 拒 PSO），
写出 DXIL 并打印上文那行 JSON。

* UMA 窗口固定为 1（与 VIctory 的单窗口根签名一致）；运行时窗口数 >1 时 XCL 的 HLSL 会不同。
* GS/MS 需要两趟管线，当前命令拒之（746 个失败因此落在覆盖外）。

## 搬运（`tools/fill_xcl_sidecar.py`）

对失败容器算**容器 BLAKE3**（与 VIctory 的 shader 缓存同一个键，完整 64 hex、
`shaders/<前两位>/` 目录镜像其布局），调用 `xcl dxil`，写 `.json` + `.dxil`。
已存在即跳过，可断点续跑；失败按原因计数——那就是两个翻译器都不覆盖的集合。
