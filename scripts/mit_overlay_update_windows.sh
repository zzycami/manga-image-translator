#!/usr/bin/env bash
# Overlay-update the Windows backup manga-image-translator from this Mac.
#
# Flow (same as the Aug 2026 manual deploy, hardened):
#   1) rsync code + detect-20241225.ckpt + Dockerfile.overlay.windows to the
#      Windows Linux env (~/mit-overlay-src)
#   2) build overlay with Dockerfile.overlay.windows:
#        - falls back to the base's pure-python paddle detector (official base
#          image has no Rust extension)
#        - bakes detect-20241225.ckpt into the image (no first-request download)
#   3) switch the container (old one renamed as backup; old image tagged .prev)
#   4) smoke: openapi stages + optional real stages call
#
# Usage (from repo root):
#   MIT_WIN_SSHPASS='<password>' ./scripts/mit_overlay_update_windows.sh
#   # or with SSH keys (no password):
#   ./scripts/mit_overlay_update_windows.sh
#
# Env overrides:
#   MIT_WIN_HOST     ssh target (default: zhouzeyong@192.168.31.156)
#   MIT_WIN_SSHPASS  password for sshpass (omit to use SSH keys)
#   MIT_WIN_DOCKER   docker.exe path on Windows (default below)
#   MIT_WIN_SRC      remote build context (default: ~/mit-overlay-src)
#   BASE_IMAGE       base image (default: zyddnys/manga-image-translator:main)
#   NEW_IMAGE        result tag (default: manga-translator:json-stages)
#   CONTAINER_NAME   container to switch (default: manga_image_translator_gpu)
#   SMOKE_IMAGE      optional page path for a real stages smoke call

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
MIT_ROOT="${MIT_ROOT:-$ROOT}"

MIT_WIN_HOST="${MIT_WIN_HOST:-zhouzeyong@192.168.31.156}"
MIT_WIN_SSHPASS="${MIT_WIN_SSHPASS:-}"
MIT_WIN_DOCKER="${MIT_WIN_DOCKER:-/mnt/c/Program Files/Docker/Docker/resources/bin/docker.exe}"
# Relative path: both rsync and the remote shell resolve it against the remote
# user's home directory (do NOT expand $HOME locally).
MIT_WIN_SRC="${MIT_WIN_SRC:-mit-overlay-src}"
BASE_IMAGE="${BASE_IMAGE:-zyddnys/manga-image-translator:main}"
NEW_IMAGE="${NEW_IMAGE:-manga-translator:json-stages}"
CONTAINER_NAME="${CONTAINER_NAME:-manga_image_translator_gpu}"
SMOKE_IMAGE="${SMOKE_IMAGE:-}"

log() { printf '[mit-win] %s\n' "$*"; }
die() { printf '[mit-win] ERROR: %s\n' "$*" >&2; exit 1; }

if [[ -n "$MIT_WIN_SSHPASS" ]]; then
  SSH_OPTS=(-o PreferredAuthentications=password -o PubkeyAuthentication=no -o StrictHostKeyChecking=accept-new)
  RSYNC_SSH="sshpass -p '$MIT_WIN_SSHPASS' ssh ${SSH_OPTS[*]}"
  ssh_cmd() { sshpass -p "$MIT_WIN_SSHPASS" ssh "${SSH_OPTS[@]}" "$MIT_WIN_HOST" "$@"; }
else
  RSYNC_SSH="ssh -o BatchMode=yes"
  ssh_cmd() { ssh -o BatchMode=yes "$MIT_WIN_HOST" "$@"; }
fi

need_file() { [[ -e "$1" ]] || die "missing: $1"; }

preflight() {
  need_file "$MIT_ROOT/Dockerfile.overlay.windows"
  need_file "$MIT_ROOT/manga_translator/stages_json.py"
  need_file "$MIT_ROOT/server/main.py"
  need_file "$MIT_ROOT/models/detection/detect-20241225.ckpt"
  command -v sshpass >/dev/null 2>&1 || [[ -z "$MIT_WIN_SSHPASS" ]] || die "sshpass not installed"
}

sync_code() {
  log "rsync code + weights -> $MIT_WIN_HOST:$MIT_WIN_SRC"
  eval "rsync -az --delete -e \"$RSYNC_SSH\" \
    --exclude '.git' --exclude 'venv' --exclude 'result' --exclude '__pycache__' --exclude '*.pyc' --exclude '.cursor' \
    '$MIT_ROOT/Dockerfile.overlay.windows' '$MIT_ROOT/scripts' '$MIT_ROOT/manga_translator' '$MIT_ROOT/server' \
    '$MIT_WIN_HOST:$MIT_WIN_SRC/'"
  # Single file -> exact remote path (rsync would flatten it otherwise).
  ssh_cmd "mkdir -p '$MIT_WIN_SRC/models/detection'"
  eval "rsync -az -e \"$RSYNC_SSH\" \
    '$MIT_ROOT/models/detection/detect-20241225.ckpt' \
    '$MIT_WIN_HOST:$MIT_WIN_SRC/models/detection/detect-20241225.ckpt'"
}

remote_build() {
  log "remote build ($BASE_IMAGE -> $NEW_IMAGE)"
  ssh_cmd 'set -e
  D="'"$MIT_WIN_DOCKER"'"
  cd "'"$MIT_WIN_SRC"'"
  grep -q "parse_indexed_translations" manga_translator/translators/common_gpt.py || { echo "missing fix marker"; exit 1; }
  # Keep the build context small: only the weights we bake, not the whole models tree.
  cat > .dockerignore <<'"'"'EOF'"'"'
.git
venv
result
__pycache__
*.pyc
.cursor
models/*
!models/detection/
!models/detection/detect-20241225.ckpt
EOF
  "$D" build -f Dockerfile.overlay.windows \
    --build-arg BASE_IMAGE="'"$BASE_IMAGE"'" \
    -t "'"$NEW_IMAGE"'" .
  echo "[mit-win] verify import + baked weights"
  "$D" run --rm --entrypoint python "'"$NEW_IMAGE"'" -c "
from manga_translator import Config
import os
assert os.path.exists(\"/app/models/detection/detect-20241225.ckpt\"), \"detect weights missing\"
print(\"image import OK + detect-20241225.ckpt baked\")
"'
}

switch_container() {
  log "switch container $CONTAINER_NAME -> $NEW_IMAGE"
  local BACKUP="${CONTAINER_NAME}_pre_json_stages"
  # NOTE: pass the whole remote script as ONE ssh argument. Docker Desktop's
  # docker.exe on WSL consumes stdin, so piping a script via 'bash -s' stalls.
  ssh_cmd 'set -e
D="'"$MIT_WIN_DOCKER"'"
"$D" inspect "'"$CONTAINER_NAME"'" --format "{{range .Config.Env}}{{println .}}{{end}}" > /tmp/mit.env
"$D" rm -f "'"$BACKUP"'" 2>/dev/null || true
"$D" stop "'"$CONTAINER_NAME"'"
"$D" rename "'"$CONTAINER_NAME"'" "'"$BACKUP"'"
"$D" run -d --name "'"$CONTAINER_NAME"'" --gpus all --env-file /tmp/mit.env \
  -v "D:\\codes\\manga-image-translator\\result:/app/result" -p 8000:8000 --entrypoint python \
  "'"$NEW_IMAGE"'" \
  server/main.py --verbose --start-instance --host=0.0.0.0 --port=8000 --use-gpu
sleep 10
"$D" ps -a --format "{{.Names}}\t{{.Image}}\t{{.Status}}\t{{.Ports}}" | grep -i manga
"$D" logs --tail 8 "'"$CONTAINER_NAME"'" 2>&1'
}

smoke() {
  log "smoke openapi"
  ssh_cmd 'D="'"$MIT_WIN_DOCKER"'"
  for i in 1 2 3 4 5 6 7 8 9 10; do
    code=$(curl -sS -m 3 -o /dev/null -w "%{http_code}" http://127.0.0.1:8000/docs || echo fail)
    echo "try $i: $code"
    [[ "$code" == "200" ]] && break
    sleep 3
  done
  curl -fsS -m 30 http://127.0.0.1:8000/openapi.json | grep -oE "/translate[^\"]*stages[^\"]*" | head -6'
  if [[ -n "$SMOKE_IMAGE" ]]; then
    need_file "$SMOKE_IMAGE"
    log "real stages smoke: $SMOKE_IMAGE"
    curl -sS -m 900 -o /tmp/mit_win_stages.json \
      -F "image=@$SMOKE_IMAGE" \
      -F 'config={"pipeline_mode":"json_stages","translator":{"translator":"custom_openai","target_lang":"CHS"},"detector":{"detector":"default","detection_size":1536},"ocr":{"ocr":"48px"},"stages_include_mask":true,"stages_include_inpainted":false}' \
      "http://$MIT_WIN_HOST:8000/translate/with-form/stages"
    python3 - <<'PY'
import json
d = json.load(open('/tmp/mit_win_stages.json'))
regs = d.get('regions') or []
assert len(regs) >= 1 and all(r.get('translatedText') for r in regs), d
print('STAGES_OK regions=%d md5=%s' % (len(regs), d.get('sourceImageMd5')))
PY
  fi
}

preflight
sync_code
remote_build
switch_container
smoke
log "done. rollback: docker tag $NEW_IMAGE $NEW_IMAGE.prev; or switch back to $CONTAINER_NAME"'_pre_json_stages'
