# Client stage pipeline（端云分工）

**Branch:** `feat/client-stage-pipeline`  
**Companion repo:** `manga-translate-native`（本机路径示例：`../manga-translate-native`）

## 目标

在保留现有 `full`（整图上传 → 全流水 → 回译图）的前提下，逐步支持：

1. `json_stages`（产品主路径）：上传原图 → 检测/OCR → 翻译 → **mask 精炼** → 下发紧凑 stages（**含 `maskPngBase64`，默认不含擦净底图**）→ 客户端用原图 + mask 做 lama 擦净（几何擦净为 fallback）→ 叠字。
2. `translate_only`：客户端已提供 OCR 文本时，云端只做翻译。

权威中间格式见 companion：`docs/SCHEMA.md`（schemaVersion `0.1.0`）。

## 本分支已落地

- [x] `Config.pipeline_mode`：`full` | `json_stages` | `translate_only`（后者预留）
- [x] `json_stages`：跳过服务端文字渲染与 **inpaint**，写入 `ctx.translation_stages`
- [x] `json_stages`：**保留 mask 精炼**；默认 `stages_include_mask=true` 附带 `maskPngBase64`
- [x] 默认不附带 `inpaintedJpegBase64`；`stages_include_inpainted=true` 可 opt-in
- [x] `fontSize` / `alignment` 写入 stages
- [x] API：`POST /translate/stages`、`POST /translate/with-form/stages`
- [x] Mac 摸底：`tools/client_pipeline/bench_client_lama.py`（同款 `lama_large` + 原图 + mask）
- [x] E2E：`tools/client_pipeline/run_e2e_client_pipeline.py`（mask→lama→native 叠字）
- [x] ONNX 导出：`tools/client_pipeline/export_lama_onnx.py`（lama_large，matmul DFT，≈206MB）
- [x] 移动端主路径：`tools/client_pipeline/export_aot_onnx.py`（AOT `inpainting.ckpt`，≈23MB；IO 同为 [0,1]）
- [x] iOS/Mac Core ML（Metal/ANE）：`tools/client_pipeline/export_aot_coreml.py`（先全量 FP32；bake ScaledWS*；产物 `result/lama_coreml/aot_{256,384}.mlpackage`）
- [x] Android ORT 冒烟：入门机 AOT@384 ≈6.8s、AOT@256 ≈3.8s（相对 lama_large@512 ≈30s）
- [ ] Hub comic-translate 透传 `pipelineMode`（TinyReader 侧）
- [x] Android ORT 接入（入门机默认 AOT；lama_large 仅高质量备用）
- [x] iOS App 接入 Core ML AOT + `mt_render`（`tinyreader`；见 `docs/MIT_DIRECT_IOS.md`；真机效果待手测）

配套：`../manga-translate-native`（几何擦净 `mt_render` ≥0.3.8 作 fallback；移动端擦净优先 AOT ONNX / iOS Core ML）

## 导出 AOT → Core ML（iOS / Mac）

```bash
# 需 coremltools（MIT venv：pip install 'coremltools>=8'）
PYTHONPATH=. ./venv/bin/python tools/client_pipeline/export_aot_coreml.py \
  --size 384 --smoke \
  --image ../manga-translate-native/result/batch_hana_timing/005_005/page_work.jpg \
  --mask  ../manga-translate-native/result/batch_hana_timing/005_005/mask_final.png
```

- 输出：`result/lama_coreml/aot_384.mlpackage`（≈23MB FP32）+ `smoke_aot_coreml_384.png`
- 数值：相对 bake 后 PyTorch，`max_abs_diff` ~1e-5；Mac 上 Core ML 推理约数十 ms（非整页 App 路径）
- 说明：coremltools 9 不再吃 ONNX；导出前把 `ScaledWSConv*` 的 `var_mean` **bake** 成普通 Conv，语义与 eval 一致

## 后续

- [ ] `translate_only` 完整接线
- [ ] 与 Hub 契约对齐（**双输出兼容旧 full**）
- [ ] 若 Mac/真机 lama 过重：蒸馏/量化后再进 App
