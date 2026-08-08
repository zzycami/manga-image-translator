# MIT detect/OCR/LLM 优化实验

分支：`perf/mit-detect-ocr-llm`

## 方法

1. 固定 3 张：`manga-translate-native/result/batch_hana_timing/{005,007,033}/page_work.jpg`
2. 脚本：`tools/client_pipeline/bench_mit_stages_ab.py`
3. stages JSON 含 `stageTimingsMs`（服务端墙钟，不受 HTTP 缓冲影响）
4. 改一档配置 → 同图复测 → `compare.json`（框 IoU / OCR 一致率 / 总耗时）

## 基线（local `:8010`，Hub 同款配置）

目录：`result/bench_mit_stages_ab/local8010_20260808_201457/baseline`

| 页 | 总耗时 | detection | ocr | textline_merge | translating | regions |
|----|--------|-----------|-----|----------------|-------------|---------|
| 005 | 4.3s | 0.54s | 0.61s | 1.02s | **1.82s** | 5 |
| 007 | 6.6s | 0.24s | **1.82s** | 1.03s | **3.03s** | 8 |
| 033 | 5.9s | 0.34s | **2.34s** | 0.70s | **2.12s** | 6 |
| **合计** | **16.8s** | | | | | |

结论：主耗时在 **OCR + textline_merge + LLM**；detection@1536 不是最大头。

## 优化 #1：`detection_size=1024`

- **耗时**：合计 16.8s → 16.4s（约 -2%），不稳定
- **质量**：框/OCR 漂 → **不采纳**

## 优化 #2：`ocr=32px`（Docker）

- **耗时**：18.2s → 24.2s（**+33%**）
- **质量**：OCR exact 差 → **不采纳**

## 优化 #3：`textline_merge` 去重复 `dispatch`（代码）

目录：`result/bench_mit_stages_ab/merge_once_20260808_205455`

- 旧实现在 `skip_lang=None` 时仍 **merge 两次**，且第一次写的 `text_raw` 被第二次丢掉
- 改为：先（可选）按语言过滤 OCR 行 → **只 merge 一次** → 在最终 region 上设 `text_raw`
- **耗时**：`textline_merge` 几乎不变（~1.0s / ~1.0s / ~0.7s）→ 瓶颈不在双次 geometry merge
- **质量**：框/OCR IoU=1.0 exact=1.0
- **裁决**：作为 **正确性修复保留**（工作树已改）；**不是**性能主刀

## 优化 #4：`force_simple_sort=true`（配置）★

目录：`result/bench_mit_stages_ab/simple_sort_20260808_205647`

| | baseline | force_simple_sort |
|--|----------|-------------------|
| 三页合计 | **16.8s** | **12.2s**（约 **-27%**） |
| textline_merge | ~1.02 / 0.99 / 0.72s | **~0.08 / 0.06 / 0.08s** |
| 框 IoU / OCR exact | — | **1.0 / 1.0**（质量闸通过） |

根因：`sort_regions(..., img=...)` 默认走 **panel 检测**；`force_simple_sort` 跳过 panel，耗时从 ~1s → ~80ms。

**阅读顺序**：005 不变；007 / 033 **region 顺序变化**（集合相同，排序不同）→ 可能影响 LLM 上下文与客户端气泡阅读序。

- **裁决（性能）**：有效，值得作为可选快路径
- **裁决（Hub 默认）**：**先不改默认**，需产品确认是否接受简单排序的阅读序；或另做更快的 panel 检测

## 优化 #5：LLM 去掉 few-shot chat sample

目录：`result/bench_mit_stages_ab/llm_nofewshot_20260808_205815`

| | baseline（有 few-shot） | no-fewshot |
|--|------------------------|------------|
| translating 007 | 2.45s | **2.74s** |
| translating 033 | 2.03s | **2.53s** |
| 合计 | 15.7s | 19.1s（首页冷启动污染） |

- **裁决**：**不采纳**（不加速；可能因缺少格式示例导致输出更长/更慢）

## 累计结论

| 改动 | 耗时 | 质量/副作用 | 采纳 |
|------|------|-------------|------|
| det 1536→1024 | ≈持平 | 框/OCR 漂 | 否 |
| ocr 48→32 | +33% | OCR 差 | 否 |
| merge 只跑一次 | ≈0 | 修 text_raw | **代码保留** |
| **force_simple_sort** | **textline_merge ~−0.9s/页；总 ~−27%** | 阅读序可能变 | **待确认是否进 Hub** |
| LLM 去 few-shot | 不加速 | — | 否 |

## 下一步候选

1. **请确认**：Hub `json_stages` 是否默认打开 `force_simple_sort`（接受阅读序简化）？
2. 若否：给 panel 检测做缓存/降分辨率，或异步与 OCR 重叠
3. LLM：换更快 ARK 端点 / 更短 system prompt（需单独 A/B）
4. OCR：仍是第二大头（~0.6–2s），需模型/实现级优化，不是分辨率刀

## iOS 探针：专用 OCR → Core ML（2026-08-08）

脚本：`tools/client_pipeline/export_ocr48_coreml.py`  
产物：`result/ocr_coreml/`

| 部件 | 结果 | 体积 |
|------|------|------|
| **encoder**（backbone+enc） | 已转 `mlprogram` iOS16；vs PT `max_abs≈1e-3`；热跑 **~16–30ms**/条（Mac） | **~102MB** |
| **decoder step0** | 已转（证明可导）；step 未做成通用循环 | **~103MB** |
| beam 解码 | 仍在 **PyTorch**（服务端同款 `beams_k=5`） | — |

冒烟（005 页，竖排 warp）：

- 单行区 exact OK（`高嶺 華` / `のはずが`）
- 合并多行区 beam 只出首行（属 stages 多边形粒度，不是 Core ML 坏了）
- 词表另需 `alphabet-all-v7.txt`（~182KB）

**产品决策（2026-08-08 早）**：曾设想体积可接受 → 端上对齐 `default@1536` + `ocr48` + `beams_k=5`。

**产品决策（2026-08-08 晚，修订）——手机端放弃端上 OCR**：

| 场景 | 裁决 |
|------|------|
| **Mac 本地漫画翻译软件** | 可行：算力/内存够，质量路径已冒烟 |
| **iOS / Android App** | **放弃端上专用 OCR**：内存不宽松；包体（det+OCR 数百 MB～GB 级 decoder 债）伤获客；推理效率尚可但工程不可上架主路径 |
| **OCR** | **继续上云**（当前无现实替代） |
| **端上仍可做** | **语言/文字区域识别（detect）→ 裁块或框信息**，减轻上传与服务器 CV；OCR/译仍云端 |

探针结论仍有效（技术储备 / Mac）：encoder+beam 质量可对齐；须逐 textline；native C ABI 已通。手机产品不跟进 `ios-det-textline-warp` 全链路 OCR。

**下一刀（手机）**：粗/精区域检测怎么控漏检——见下「未决」与 Vision 探针。

## iOS 探针：系统 Vision（2026-08-08）

脚本：`tools/client_pipeline/bench_vision_ocr_mac.swift`  
对照：`result/bench_mit_stages_ab/simple_sort_…/baseline` 三页  
结果目录：`result/bench_vision_ocr_mac/scale*_…`

| | Vision 算力 | 质量 |
|--|-------------|------|
| `VNRecognizeTextRequest`（ja accurate） | **很快**（~0.1–0.2s/页，Mac） | **不可用**：OCR 命中 0～2 条 vs MIT 5～8 区；exact/soft≈0 |
| `VNDetectTextRectangles` | 同上量级 | **有信号**：005/007/033 → 10/21/9 框（未合并），接近「有字区域」 |

结论：

- **纯 B（端上 Vision OCR → 只传文本）对日漫：否决**（认不出字，不是算力问题）。
- **算力在 Apple 上不是瓶颈**；瓶颈是 **漫画字体/竖排/气泡** 超出通用 OCR。
- **更可行的过渡**：端上 **只检测（Vision 框或日后 CTD）→ 裁块上传 → 云端 OCR+译**（方案 A）；全量自研 OCR Core ML 仍是重活。
- App 内已有 `AutoTranslator`（Vision ja）— 与探针一致，不宜当漫画主路径。

## 本轮尝试结束（2026-08-08）

MIT 性能 / 端上 OCR·检测探针**到此为止**。结论：配置与探针范围内**已无明显可上线优化点**；手机不上专用 OCR；开源保下限、产品靠自研。

**后续（不急）**：正式 MIT 服务有更新后再陆续推客户端（现有 AOT / `mt_render` / stages 契约等）。检测小模型（comic-text-detector 方向）与区域召回留作更远期，非本轮交付。

上游 `zyddnys/manga-image-translator` `main` 已核对（push 至 2026-07-20）：近期无 detect/OCR/inpaint 主路径加速。

## 开源生态观察（2026-08-08）

立场：**开源只保证下限；要做成更好的上线漫画翻译产品，只能自己做。** 外部项目作参考与对标，持续观察，不指望上游替我们交付竞争力。

| 项目 | 协议 | 对我们 | 观察点 |
|------|------|--------|--------|
| [zyddnys/manga-image-translator](https://github.com/zyddnys/manga-image-translator) | GPL-3.0 | 现网 fork 根基；CV 主路径近期无明显加速 | `main` / Rust 旁支 |
| [manga-image-translator-rust](https://github.com/frederik-uni/manga-image-translator-rust) | （独立） | 部署/内存或可略好；难解 LLM 瓶颈；迁契约成本高 | 成熟度、API 稳定性 |
| [kha-white/manga-ocr](https://github.com/kha-white/manga-ocr) | Apache-2.0 | MIT 已可选 `mocr`；非端上解法 | 质量 vs ocr48 |
| [ogkalu2/comic-translate](https://github.com/ogkalu2/comic-translate) | Apache-2.0 | 产品/多语 LLM；RT-DETR 气泡检测可对照 | 检测召回、桌面/扩展形态 |
| [dmMaze/BallonsTranslator](https://github.com/dmMaze/BallonsTranslator) | GPL-3.0 | 桌面 CAD + 依赖 MIT；LLM 上下文/术语、[comic-text-detector](https://github.com/dmMaze/comic-text-detector) | 人机协作、译后编辑 UX |
| [alicewish/MomoTranslator](https://github.com/alicewish/MomoTranslator) | MIT | **OpenCV 画格/气泡粗检**思路；轻量端上区域参考；漏检风险高 | 启发式召回下界 |
| `~/Documents/GitHub/comic-text-detector`（dmMaze） | GPL-3.0 | **检测重训主仓**：YOLOv5 block + DB line + mask；已有 ONNX；≈MIT `Detector.ctd` | 召回优先小模型 / 数据闭环 |
| `~/Documents/GitHub/anime-inpainting-deq`（zyddnys） | （WIP） | AOT/Lama **训练草稿**；DEQ 未完成（多文件空壳）；非手机优先 | 仅擦净质量不够时再碰 |

产品路径（已定，观察不改变）：

- 手机：**OCR 上云**；放弃端上专用 OCR（内存/包体）。
- 端上可选远期：**区域粗检**（高召回 + 漏检回退整页），须自测相对 MIT 框的 recall。
- Mac 本地全链路 OCR：技术上可行，非手机主路径。
- 真要拉开差距：检测召回策略、Hub 契约、LLM 译质/成本、端上擦净叠字（已有 AOT/`mt_render`）——**自研迭代**。

## 未决

- 译文 exact 低属 LLM 非确定性；检测/OCR 优化以框+`sourceText` 为准
- Hub 默认是否启用 `force_simple_sort`
- **区域检测漏字**：Vision `DetectTextRectangles` 有信号但未严格测 recall；粗检漏了 = 云端永远看不到该字。需定策略：高召回阈值 / 多尺度 / 漏检时回退整页上云 / 与 MIT default 框对比测 recall
- 是否做「端上框 → 裁块上传 → 云 OCR+译」契约（方案 A）；专用 det 模型体积是否可接受（仅 det、无 OCR）
