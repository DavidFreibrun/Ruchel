#!/usr/bin/env bash
# Download the ASR models used by tools/transcribe.py into ./models
# (GitHub release assets — no Hugging Face access required).
set -euo pipefail

MODEL="${1:-small}"          # small | medium | turbo | tiny | base | small.en ...
DEST="${ASR_MODELS_DIR:-models}"
BASE="https://github.com/k2-fsa/sherpa-onnx/releases/download/asr-models"

mkdir -p "$DEST"
cd "$DEST"

[ -f silero_vad.onnx ] || curl -sSL -O "$BASE/silero_vad.onnx"

if [ ! -d "sherpa-onnx-whisper-$MODEL" ]; then
  curl -sSL -o "whisper-$MODEL.tar.bz2" "$BASE/sherpa-onnx-whisper-$MODEL.tar.bz2"
  tar xf "whisper-$MODEL.tar.bz2"
  rm "whisper-$MODEL.tar.bz2"
fi

echo "models ready in $PWD:"
du -sh silero_vad.onnx "sherpa-onnx-whisper-$MODEL"
