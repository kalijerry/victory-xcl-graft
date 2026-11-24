# 泄露包不完整：怎么查、怎么修

2026-11-24 我们撞的墙不是代码，是数据。记录在这里，省下别人几小时。

## 症状

两个互不相关的项目在同一个位置死掉：

* DirectStorage zlib 请求失败 `0x8007000d`（`anim.rpf` 偏移 `0xD7D2E420` 附近）；
* 标题在 `game_scarlett_master.exe+0x4da6315` 执行 `int3`（`cc 31 c0 c3`＝`__debugbreak` + 返回 0），
  崩溃上下文是 `fbk_stry000_FBK_STRY000_INTRO` / `Prestream` / `System Init` / `Frame 0`。
* 直接读该偏移：连续 16 MiB 全是 0 —— 不是合法空隙，是洞。

## 查

用种子**自带的 piece hash** 全量校验，不猜：
`tools/verify_pieces.py`（先要 `bad-pieces.json`，用同种子的 `info/pieces` 逐 piece 比 SHA-1）。
结果总量级是**整包不完整**，不是单点：

```
76 / 13,345 pieces bad = 1.19 GiB
audio.rpf 23, movies.rpf 13, anim.rpf 7, navmesh 3, ttdb maps/terrain/interiors …, 
```

`anim.rpf` 只是第一个被读到的。

## 修（qBittorrent）

1. 用原 `.torrent` 加回客户端、指向同一目录，**全量 recheck**；
2. 客户端只拉坏 piece；
3. 期间**不要启动标题**：客户端持着档案的写句柄，读方只请求 `FILE_SHARE_READ` 会拿到
   `ERROR_SHARING_VIOLATION 32`，标题 2–3 s 内断言死。修补丁见 `patches/xcl/0003`
   （VIctory 侧同理改 dstorage 的打开）。

### 大坑：不要信客户端的 resume 状态

本轮客户端的 `.fastresume` 里 piece 位图是**空的**（0 字节），它以为一个 piece 都没有，
准备重下 208 GB（≈9 小时），于是坏 piece 几乎不动。把校验器算出的真实 `pieces` 位图写进
resume 数据（libtorrent 认 `pieces` 键，认 `bitfield` 键不生效），重启客户端后它会跳到
99.9x%，只拉剩下的 11 个 piece，**一分钟**完成。

## 验收

`tools/verify_pieces.py` 必须报 `remaining_bad: 0`。本轮最后 76/76 全部与种子 hash 一致。

## 顺带两条

* 修复会把 `game_scarlett_master.exe` 换回官方件；本仓库的 `tools/patch_exe.py` 负责把
  9 处本地补丁打回去（8 处"拿 0 当全局"的 `int3` 断言 + `anim` 路径的 `int3`）。
  recheck 期间不要反复打补丁——客户端会把 exe 又拉一遍。
* 建议给两个项目的 preflight 加一道数据完整性闸（每文件 BLAKE3 对照 manifest，或全档案零游程扫描），
  这一类洞在一个 boot 之前就该被拦住。
