#!/bin/bash
# DIVAN-COZ denetimli ince ayar - TRUBA cuda-ui (ARF-ACC)
#
# Kosum:
#   sbatch scripts/truba/sft.slurm
#
# TRUBA kurallari (bu arayuzde gecerli):
#   - Bu kumede yalnizca iki kuyruk var: kolyoz-cuda (H100/H200), palamut-cuda (A100)
#   - Her is EN AZ 16 cekirdek + 1 GPU ister; GPU'suz is bu kuyruklarda calismaz
#   - kolyoz-cuda'da GPU tipi -C ile secilir: H100 veya H200
#   - Agir hesap login node'da (cuda-ui) CALISTIRILMAZ
#   - /arf altina pip/conda ile kurulum YAPILMAZ; merkezi modul kullanilir

#SBATCH --job-name=divan-coz-sft
#SBATCH --partition=kolyoz-cuda
#SBATCH --constraint=H100
#SBATCH --gres=gpu:1
#SBATCH --cpus-per-task=16
#SBATCH --time=12:00:00
#SBATCH --output=logs/%x-%j.out
#SBATCH --error=logs/%x-%j.err

set -euo pipefail

SCRATCH="/arf/scratch/${USER}"
PROJE="${SCRATCH}/sesver"

mkdir -p "${PROJE}/logs" "${PROJE}/checkpoints"
cd "${PROJE}"

module purge
module load apps/truba-ai/gpu-2024.0

echo "=============================================="
echo " is kimligi   : ${SLURM_JOB_ID}"
echo " kuyruk       : ${SLURM_JOB_PARTITION}"
echo " dugum        : $(hostname)"
echo " baslangic    : $(date -Is)"
echo "=============================================="
nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader

export PYTHONPATH="${PROJE}/src:${PYTHONPATH:-}"
export TOKENIZERS_PARALLELISM=false
export HF_HOME="${SCRATCH}/.cache/huggingface"
export OMP_NUM_THREADS="${SLURM_CPUS_PER_TASK}"

# SFT verisi commit edilmez (tohumla yeniden uretilebilir); egitimden hemen
# once uretilir - bkz. src/sesver/models/sft_veri.py
srun python -m sesver.models.sft_veri \
  --egitim-cikti      "data/sft_train.jsonl" \
  --dogrulama-cikti   "data/sft_val.jsonl"

srun python -m sesver.models.train_sft \
  --taban-model "Qwen/Qwen3-1.7B" \
  --veri        "data/sft_train.jsonl" \
  --dogrulama   "data/sft_val.jsonl" \
  --cikti       "checkpoints/divan-coz-${SLURM_JOB_ID}" \
  --epoch 3 \
  --lr 1e-4

echo " bitis: $(date -Is)"

# Egitim biter bitmez degerlendirme kapisi kosar.
# SES VER-Bench'te gerileme varsa adaptor YAYINA ALINMAZ.
srun python -m sesver.cli bench --messages 20000 --seed 7 \
  --json "checkpoints/divan-coz-${SLURM_JOB_ID}/bench.json"
