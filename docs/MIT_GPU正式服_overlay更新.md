# MIT GPU 正式服 Overlay 更新手册

适用场景：在 **已有模型权重的基础镜像**上，只热更新 `server/` + `manga_translator/`（含 `json_stages`、计时字段等代码），**不重新下载**多 GB 模型。

| 项 | 值 |
|----|-----|
| 正式机 | `ubuntu@106.75.246.172`（SSH 公钥登录；**不要用 root**） |
| Hub 配置 | `translate.local-manga.servers` → `http://106.75.246.172:8000`（另有 `diffusion.pivlite.com:7001`） |
| Compose 目录 | `/home/ubuntu/manga-translator` |
| 构建上下文 | `/home/ubuntu/mit-overlay-src`（本机 rsync 上去） |
| 运行容器名 | `manga_image_translator_gpu` |
| 基础镜像（含模型） | `manga-translator-backup:latest` |
| 业务镜像（代码 overlay） | `manga-translator:json-stages` |
| 监听 | 宿主机 `8000` → 容器 `8000` |
| 本仓配方 | 根目录 `Dockerfile.overlay`；脚本 `scripts/mit_overlay_update.sh`（通用；正式机常用下方「手工/rsync」流程） |

最近一次成功更新：**2026-08-09**（`main`：stages 计时、`textline_merge` 一次、`to_json` Pydantic v2 修复）。

---

## 0. 更新前检查

在开发机：

```bash
cd /Users/zhouzeyong/Documents/GitHub/manga-image-translator
git checkout main
git status   # 确认要上线的提交已在本地 main
test -f Dockerfile.overlay
test -f manga_translator/stages_json.py
```

在正式机：

```bash
ssh ubuntu@106.75.246.172 'docker ps --format "{{.Names}}\t{{.Image}}\t{{.Status}}" | grep manga'
# 期望：manga_image_translator_gpu   manga-translator:json-stages   Up ...
```

可选：短暂停外网隧道 / 观察 Hub 队列，避免更新瞬间高峰（非必须）。

---

## 1. 同步代码到正式机

在开发机执行（排除缓存；约 10MB 级）：

```bash
REMOTE=ubuntu@106.75.246.172
SRC=/Users/zhouzeyong/Documents/GitHub/manga-image-translator
DST=/home/ubuntu/mit-overlay-src

ssh "$REMOTE" "mkdir -p $DST"
rsync -az --delete \
  --exclude '__pycache__' --exclude '*.pyc' --exclude '.DS_Store' \
  "$SRC/manga_translator/" "$REMOTE:$DST/manga_translator/"
rsync -az --delete \
  --exclude '__pycache__' --exclude '*.pyc' \
  "$SRC/server/" "$REMOTE:$DST/server/"
scp -q "$SRC/Dockerfile.overlay" "$REMOTE:$DST/Dockerfile.overlay"
```

`Dockerfile.overlay` 内容要点：`FROM ${BASE_IMAGE}` → `COPY manga_translator` + `COPY server`。

---

## 2. 构建 overlay 镜像并切换 Compose

```bash
ssh ubuntu@106.75.246.172 'set -euo pipefail
cd /home/ubuntu/mit-overlay-src
docker build -f Dockerfile.overlay \
  --build-arg BASE_IMAGE=manga-translator-backup:latest \
  -t manga-translator:json-stages .

cd /home/ubuntu/manga-translator
# 首次从 backup 切到 json-stages 时改 image；已是 json-stages 则只需 recreate
cp -a docker-compose.yml "docker-compose.yml.bak.$(date +%Y%m%d%H%M%S)"
grep -q "manga-translator:json-stages" docker-compose.yml \
  || sed -i -E "s|image:[[:space:]]*manga-translator-backup:[^[:space:]]+|image: manga-translator:json-stages|" docker-compose.yml

docker compose up -d --force-recreate
sleep 12
docker ps --format "{{.Names}}\t{{.Image}}\t{{.Status}}" | grep manga
'
```

`docker-compose.yml` 中应保持：

- `image: manga-translator:json-stages`
- `container_name: manga_image_translator_gpu`
- `ports: "8000:8000"`
- 挂载 `./result`、`./default_config.json`（只读）
- `runtime: nvidia` 与现有 `CUSTOM_OPENAI_*` / `DEFAULT_TRANSLATOR` 等环境变量（**不要在文档或 git 里提交密钥**）

模型仍在基础镜像层内；compose **未**挂 `./models` 时不要删 `manga-translator-backup:latest`。

---

## 3. 冒烟（必须新旧都测）

开发机对公网端口测（也可用 `ssh` 后打 `127.0.0.1:8000`）。

准备一张小图，例如：

`result/client_stage_smoke/page_1600.jpg`

### 3.1 OpenAPI

```bash
HOST=http://106.75.246.172:8000
curl -fsS -m 30 "$HOST/openapi.json" | grep -E 'with-form/(image|stages)' 
# 必须能看到 stages；若 openapi 500，见下文「已知坑」
```

### 3.2 旧接口（整图 / Hub 现网 full）

```bash
IMG=result/client_stage_smoke/page_1600.jpg
OUT=result/prod_smoke_manual
mkdir -p "$OUT"
CFG_FULL='{"pipeline_mode":"full","translator":{"translator":"custom_openai","target_lang":"CHS"},"detector":{"detector":"default","detection_size":1536},"ocr":{"ocr":"48px"}}'

curl -sS -o "$OUT/full.png" -w "http=%{http_code} bytes=%{size_download}\n" \
  -F "image=@${IMG}" -F "config=${CFG_FULL}" --max-time 900 \
  "$HOST/translate/with-form/image"
file "$OUT/full.png"   # 期望 PNG/JPEG

# Hub 实际走流式：
curl -sS -N -o "$OUT/full.stream" -w "http=%{http_code}\n" \
  -F "image=@${IMG}" -F "config=${CFG_FULL}" --max-time 900 \
  "$HOST/translate/with-form/image/stream"
# 流内应出现 PNG 魔数 \x89PNG
```

### 3.3 新接口（json_stages / Hub AOT 路径）

```bash
CFG_STAGES='{"pipeline_mode":"json_stages","translator":{"translator":"custom_openai","target_lang":"CHS"},"detector":{"detector":"default","detection_size":1536},"ocr":{"ocr":"48px"},"stages_include_mask":true,"stages_include_inpainted":false}'

curl -sS -o "$OUT/stages.json" -w "http=%{http_code} bytes=%{size_download}\n" \
  -F "image=@${IMG}" -F "config=${CFG_STAGES}" --max-time 900 \
  "$HOST/translate/with-form/stages"

python3 - <<'PY'
import json
from pathlib import Path
d=json.loads(Path("result/prod_smoke_manual/stages.json").read_text())
assert d.get("pipelineMode")=="json_stages"
assert d.get("schemaVersion")
assert len(d.get("regions") or [])>=1
print("regions", len(d["regions"]), "timings", bool(d.get("stageTimingsMs")))
for i,r in enumerate(d["regions"][:8]):
    print(i, (r.get("sourceText") or "")[:40], "=>", (r.get("translatedText") or "")[:40])
PY

# Hub 流式：
curl -sS -N -o "$OUT/stages.stream" -w "http=%{http_code}\n" \
  -F "image=@${IMG}" -F "config=${CFG_STAGES}" --max-time 900 \
  "$HOST/translate/with-form/stages/stream"
```

**验收标准**

| 检查 | 通过条件 |
|------|----------|
| OpenAPI | HTTP 200，含 `/translate/with-form/stages` |
| full 图 | HTTP 200，文件为图像，气泡内为中文 |
| stages JSON | HTTP 200，`regions`≥1，译文非空；可选有 `stageTimingsMs`、`maskPngBase64` |
| 流式 | Hub 用的 `image/stream` / `stages/stream` 均为 200 |

仅看 OpenAPI **不够**；至少跑一轮 full + stages（阻塞或流式）。

也可：`./scripts/client_stage_smoke.sh "$IMG" "$HOST"`（默认 config 里 translator 可能是 `offline`，正式服请改成 `custom_openai` 或与 Hub 一致）。

---

## 4. 回滚

```bash
ssh ubuntu@106.75.246.172 '
cd /home/ubuntu/manga-translator
# 看备份
ls -lt docker-compose.yml.bak.* | head
# 恢复某一版后：
# cp -a docker-compose.yml.bak.YYYYMMDDHHMMSS docker-compose.yml
# 或直接改回：
#   image: manga-translator-backup:latest
docker compose up -d --force-recreate
'
```

回滚到 `manga-translator-backup:latest` 会失去 `json_stages`（旧 backup 无 stages 代码时）。更稳：保留上一版 `manga-translator:json-stages` 的镜像 tag（构建前 `docker tag manga-translator:json-stages manga-translator:json-stages.prev`）。

---

## 5. 已知坑

1. **`/openapi.json` 500 / Pydantic + `np.ndarray`**  
   `server/to_json.py` 里 `Translation.background` 必须是 **str（base64）**，不能在 OpenAPI 模型里直接挂 `numpy.ndarray`（Pydantic v2）。否则服务能起、docs 偶发可用，但 openapi 冒烟失败。  
   2026-08-09 已修：`encode_background` 在构造 `Translation` 时写入。

2. **不要用 `root` SSH**  
   正式机账号是 `ubuntu`。

3. **GitHub `git push` 可能很慢/卡住**  
   更新正式服以 **rsync 本地 tree** 为准，不必等 remote push 成功。

4. **`force_simple_sort`**  
   性能实验结论有效，但 **未** 作为 Hub/正式服默认；上线勿擅自改 `default_config.json` 除非产品确认阅读序。

5. **密钥**  
   compose 内 `CUSTOM_OPENAI_*` / DeepSeek 等只留在服务器；文档与仓库勿写入真实 key。

---

## 6. 与脚本 `mit_overlay_update.sh` 的关系

`scripts/mit_overlay_update.sh` 封装了 build / 改 compose / smoke，适合「代码已在构建机本地、且 `COMPOSE_DIR` 指向 compose」的环境。

正式机当前习惯是：**开发机 rsync → 正式机 docker build → compose recreate**（上文第 1–3 节）。若以后把仓库 clone 到 GPU 机，可：

```bash
COMPOSE_DIR=/home/ubuntu/manga-translator \
BASE_IMAGE=manga-translator-backup:latest \
NEW_IMAGE=manga-translator:json-stages \
CONTAINER_NAME=manga_image_translator_gpu \
SMOKE_URL=http://127.0.0.1:8000 \
./scripts/mit_overlay_update.sh --apply-compose
```

（需在 GPU 机上已有完整 git checkout 与 `Dockerfile.overlay`。）

---

## 7. 更新记录（摘要）

| 日期 | 内容 |
|------|------|
| 2026-08-09 | 首次从 `manga-translator-backup:latest` overlay 到 `json-stages`；修 `to_json` OpenAPI；冒烟 full + stages（含 stream）通过 |
| 2026-08-15 | 上线「译文按编号归位 + 每请求结果队列」修复（`98168f5`）；Windows 与正式服同步更新 |

---

## 8. Windows 备用机（diffusion.pivlite.com:7001）更新

备用机 = 局域网的 Windows（Docker Desktop），通过 frp 穿透暴露为
`http://diffusion.pivlite.com:7001`。它的 Linux 环境 SSH 可达（如
`zhouzeyong@192.168.31.156`），更新方式与正式机一致：**先 Windows、后正式服**。

### 一键脚本（推荐）

在开发机（Mac）仓库根目录执行：

```bash
MIT_WIN_SSHPASS='<Windows Linux 的 SSH 密码>' \
SMOKE_IMAGE=result/client_stage_smoke/page_1600.jpg \
./scripts/mit_overlay_update_windows.sh
```

脚本会：rsync 代码 + `detect-20241225.ckpt` + `Dockerfile.overlay.windows` 到
`~/mit-overlay-src` → 用 Windows 专用 Dockerfile 构建（自动切回基础镜像自带的
`paddle` 检测器、并把检测权重烤进镜像）→ 备份并切换容器 → 冒烟。

密码也可走 SSH 密钥（不设 `MIT_WIN_SSHPASS` 即可）。更多参数见脚本头部注释。

### Windows 与正式机的基础镜像差异（务必知道）

Windows 基础镜像是官方 `zyddnys/manga-image-translator:main`，**缺两样东西**，
`Dockerfile.overlay.windows` 已自动处理：

1. **没有 Rust 检测扩展**（`rusty_manga_image_translator`）——当前 main 的
   `detection/__init__.py` 引用 `.paddle_rust` 会直接启动崩溃。Windows 构建会把
   该行改回基础镜像自带的 `.paddle`。
2. **没有 `detect-20241225.ckpt`**（294MB）——默认检测器第一次请求会重新下载。
   Windows 构建把权重 COPY 进镜像，重建不再触发下载。

正式机基础镜像是自建 `manga-translator-backup:latest`，两者都有，继续用通用
`Dockerfile.overlay` 即可，不要混用。

### 手工更新（不跑脚本时）

```bash
# 1) rsync 代码 + 权重 + Windows Dockerfile
REMOTE=zhouzeyong@192.168.31.156
rsync -az --delete -e "sshpass -p '<密码>' ssh -o PreferredAuthentications=password -o PubkeyAuthentication=no" \
  --exclude '.git' --exclude 'venv' --exclude 'result' --exclude '__pycache__' --exclude '*.pyc' \
  ./Dockerfile.overlay.windows ./scripts ./manga_translator ./server \
  ./models/detection/detect-20241225.ckpt "$REMOTE:~/mit-overlay-src/"

# 2) 远程构建（.dockerignore 需排除 models/* 但放行 detect-20241225.ckpt）
ssh "$REMOTE" 'cd ~/mit-overlay-src && \
  "/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe" build \
  -f Dockerfile.overlay.windows --build-arg BASE_IMAGE=zyddnys/manga-image-translator:main \
  -t manga-translator:json-stages .'

# 3) 切换容器（先 docker tag 旧镜像为 .prev，再停/改名/起新容器），4) 冒烟 8000
```
