# Client stage pipeline（端云分工）

**Branch:** `feat/client-stage-pipeline`  
**Companion repo:** `manga-translate-native`（本机路径示例：`../manga-translate-native`）

## 目标

在保留现有 `full`（整图上传 → 全流水 → 回译图）的前提下，逐步支持：

1. `json_stages`：服务端跑到翻译（及可选 mask），返回与 native 一致的 JSON；客户端 `mt_render_rgba` 叠字。
2. `translate_only`：客户端已提供 OCR 文本时，云端只做翻译。

权威中间格式见 companion：`docs/SCHEMA.md`（schemaVersion `0.1.0`）。

## 本分支已落地（Phase 1）

- [x] `Config.pipeline_mode`：`full` | `json_stages` | `translate_only`（后者预留）
- [x] `json_stages`：跳过服务端文字渲染，写入 `ctx.translation_stages`
- [x] `manga_translator/stages_json.py`：SCHEMA 0.1.0 序列化
- [x] API：`POST /translate/stages`、`POST /translate/with-form/stages`
- [ ] Hub comic-translate 透传 `pipelineMode`（TinyReader 侧）
- [ ] 导出端侧模型（后续 Phase 2）

配套：`../manga-translate-native`（`mt_render_rgba` Phase 1 先画框底，字形后续 FreeType）

## 本分支计划改动（后续）

- [ ] `translate_only` 完整接线
- [x] 可选 `inpaintedJpegBase64` / `skipRegionFill`（擦净底供客户端叠字）
- [x] `fontSize` / `alignment` 写入 stages
- [ ] 与 Hub 契约对齐（TinyReader 不直连本服务裸端口；**产品侧需双输出兼容旧 full**）