#!/bin/bash
# TRUBA'da ilk kurulum kontrol listesi.
#
#   bash scripts/truba/kurulum.sh
#
# Bu betik HICBIR SEY KURMAZ. Ortamin hazir olup olmadigini dogrular ve
# eksikleri raporlar. /arf altina pip/conda ile kurulum yapmak kume
# kurallarina aykiridir; eksik kutuphane cikarsa cozum merkezi modul veya
# apptainer imajidir, kullanici kurulumu degildir.

set -uo pipefail

SCRATCH="/arf/scratch/${USER}"
PROJE="${SCRATCH}/sesver"
hata=0

baslik() { printf "\n\033[1m%s\033[0m\n" "$1"; }
ok()     { printf "  [ok]   %s\n" "$1"; }
uyari()  { printf "  [!]    %s\n" "$1"; }
kotu()   { printf "  [HATA] %s\n" "$1"; hata=1; }

baslik "1. Calisma dizini"
if [[ -d "${SCRATCH}" ]]; then
  ok "scratch mevcut: ${SCRATCH}"
  mkdir -p "${PROJE}/logs" "${PROJE}/checkpoints" "${PROJE}/data"
  ok "proje dizinleri hazir: ${PROJE}"
else
  kotu "scratch bulunamadi: ${SCRATCH}"
fi

baslik "2. Modul"
module purge 2>/dev/null || true
if module load apps/truba-ai/gpu-2024.0 2>/dev/null; then
  ok "apps/truba-ai/gpu-2024.0 yuklendi"
else
  kotu "merkezi AI modulu yuklenemedi"
fi

baslik "3. Python ve kutuphaneler"
if command -v python >/dev/null; then
  ok "python: $(python --version 2>&1)"
  for paket in torch transformers peft trl datasets; do
    if python -c "import ${paket}" 2>/dev/null; then
      surum=$(python -c "import ${paket}; print(getattr(${paket}, '__version__', '?'))" 2>/dev/null)
      ok "${paket} ${surum}"
    else
      uyari "${paket} yok - merkezi modulde eksik, apptainer imaji gerekebilir"
    fi
  done
else
  kotu "python bulunamadi"
fi

baslik "4. Kuyruklar"
if command -v sinfo >/dev/null; then
  sinfo -o "%.16P %.6a %.10l %.6D %.12T %N" 2>/dev/null | grep -E "PARTITION|cuda" || uyari "cuda kuyrugu listelenemedi"
  ok "kullanilabilir kuyruklar: kolyoz-cuda (H100/H200), palamut-cuda (A100)"
else
  kotu "sinfo yok - SLURM ortaminda degilsiniz"
fi

baslik "5. Cekirdek boru hatti (GPU gerektirmez)"
if PYTHONPATH="${PROJE}/src" python -m sesver.cli demo --messages 500 >/dev/null 2>&1; then
  ok "sesver cekirdegi kosuyor"
else
  uyari "cekirdek kosmadi - once depoyu ${PROJE} altina kopyalayin"
fi

baslik "Sonuc"
if [[ ${hata} -eq 0 ]]; then
  printf "  Ortam hazir. Egitimi baslatmak icin:\n\n    sbatch scripts/truba/sft.slurm\n\n"
else
  printf "  Eksikler var, yukaridaki [HATA] satirlarina bakin.\n\n"
fi
exit ${hata}
