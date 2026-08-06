# Client stage pipeline（端云分工）

**Branch:** `feat/client-stage-pipeline`  
**Companion repo:** `manga-translate-native`（本机路径示例：`../manga-translate-native`）

## 目标

在保留现有 `full`（整图上传 → 全流水 → 回译图）的前提下，逐步支持：

1. `json_stages`：服务端跑到翻译（及可选 mask），返回与 native 一致的 JSON；客户端 `mt_render_rgba` 叠字。
2. `translate_only`：客户端已提供 OCR 文本时，云端只做翻译。

权威中间格式见 companion：`docs/SCHEMA.md`（schemaVersion `0.1.0`）。

## 本分支计划改动（MIT）

- [ ] API / config 增加 `pipelineMode`（或等价字段）
- [ ] `json_stages` 响应：序列化 regions（框、源文、译文、颜色、方向）
- [ ] 可选：跳过 raster render 以省 GPU/带宽
- [ ] 导出端侧模型说明（ONNX/MNN）与版本标签，供 native Release 使用
- [ ] 与 Hub comic-translate 契约对齐（TinyReader 不直连本服务裸端口）

## 非目标（本分支早期）

- 不删除 `full` 模式
- 不把 C++/JNI 实现放进本 Python 仓

## 本地 WIP 说明

创建本分支前，若 `main` 上有未提交改动，已 `git stash`（信息含 `wip before feat/client-stage-pipeline`）。需要时在 `main` 上 `git stash pop`。
