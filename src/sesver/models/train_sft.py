"""DIVAN-COZ: Turkce adres/alan cikarimi icin QLoRA denetimli ince ayar.

Neden kendi modelimizi egitiyoruz? Iki gerekce, ikisi de savunulabilir:

  1. AFETTE ILK OLEN SEY AG BAGLANTISIDIR.
     Bulut API'sine erisilemez. Model, koordinasyon merkezindeki dizustunde
     -hatta sahadaki gonullunun telefonunda- calismak zorundadir. Bu, 1-3B
     boyut ve INT4 kuantizasyon demektir. "Neden hazir API kullanmadiniz"
     sorusunun cevabi bu tek cumledir.

  2. PANIKLE YAZILMIS TURKCE ADRES CIKARIMINI KURESEL MODELLER YAPAMAZ.
     Mahalle adlari, yerel referanslar, yarim cumleler, Turkce klavyesiz
     yazim. Bu kendi basina bir NLP problemidir.

Kosum (TRUBA):
    sbatch scripts/truba/sft.slurm

Cikti: LoRA adaptoru + egitim gunlugu + model karti taslagi.
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path

SISTEM_ISTEMI = (
    "Sen bir afet koordinasyon asistanisin. Verilen sosyal medya mesajindan "
    "yardim cagrisi alanlarini cikar ve YALNIZCA JSON dondur. "
    "Emin olmadigin alani null birak; tahmin etme."
)

# Cikti semasi boru hattindaki Konum/Cagri ile birebir ortusur.
CIKTI_SEMASI = {
    "il": "string|null",
    "ilce": "string|null",
    "mahalle": "string|null",
    "sokak": "string|null",
    "bina": "string|null",
    "kat": "int|null",
    "kisi_sayisi": "int|null",
    "kirilgan": "bool",
    "ses_var": "bool",
}


@dataclass
class EgitimAyari:
    taban_model: str = "Qwen/Qwen3-1.7B"
    cikti: str = "checkpoints/divan-coz"
    veri: str = "data/sft_train.jsonl"
    dogrulama: str = "data/sft_val.jsonl"

    # QLoRA
    lora_r: int = 32
    lora_alpha: int = 64
    lora_dropout: float = 0.05
    hedef_modul: tuple[str, ...] = (
        "q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj",
    )

    # Optimizasyon
    lr: float = 1e-4
    epoch: int = 3
    batch: int = 8
    grad_birikim: int = 4
    max_uzunluk: int = 1024
    warmup_orani: float = 0.03
    bf16: bool = True
    gradyan_kontrol: bool = True

    seed: int = 42


def istem_kur(mesaj: str) -> str:
    return (
        f"<|system|>\n{SISTEM_ISTEMI}\n"
        f"Sema: {json.dumps(CIKTI_SEMASI, ensure_ascii=False)}\n"
        f"<|user|>\n{mesaj}\n<|assistant|>\n"
    )


def ornek_bicimle(kayit: dict) -> dict:
    """jsonl satirini {metin} egitim ornegine cevirir."""
    hedef = json.dumps(kayit["alanlar"], ensure_ascii=False)
    return {"text": istem_kur(kayit["mesaj"]) + hedef}


def egit(ayar: EgitimAyari) -> None:
    # Agir bagimliliklar yalnizca burada ice aktarilir; cekirdek onlarsiz kosar.
    import torch
    from datasets import load_dataset
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    from transformers import (
        AutoModelForCausalLM,
        AutoTokenizer,
        BitsAndBytesConfig,
        TrainingArguments,
    )
    from trl import SFTTrainer

    Path(ayar.cikti).mkdir(parents=True, exist_ok=True)

    kuantizasyon = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )

    tokenizer = AutoTokenizer.from_pretrained(ayar.taban_model, trust_remote_code=True)
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        ayar.taban_model,
        quantization_config=kuantizasyon,
        torch_dtype=torch.bfloat16,
        device_map={"": 0},
        trust_remote_code=True,
    )
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(
        model,
        LoraConfig(
            r=ayar.lora_r,
            lora_alpha=ayar.lora_alpha,
            lora_dropout=ayar.lora_dropout,
            target_modules=list(ayar.hedef_modul),
            bias="none",
            task_type="CAUSAL_LM",
        ),
    )
    model.print_trainable_parameters()

    veri = load_dataset(
        "json", data_files={"train": ayar.veri, "validation": ayar.dogrulama}
    ).map(ornek_bicimle, remove_columns=["mesaj", "alanlar"])

    egitici = SFTTrainer(
        model=model,
        train_dataset=veri["train"],
        eval_dataset=veri["validation"],
        tokenizer=tokenizer,
        dataset_text_field="text",
        max_seq_length=ayar.max_uzunluk,
        packing=True,
        args=TrainingArguments(
            output_dir=ayar.cikti,
            num_train_epochs=ayar.epoch,
            per_device_train_batch_size=ayar.batch,
            gradient_accumulation_steps=ayar.grad_birikim,
            learning_rate=ayar.lr,
            warmup_ratio=ayar.warmup_orani,
            lr_scheduler_type="cosine",
            bf16=ayar.bf16,
            gradient_checkpointing=ayar.gradyan_kontrol,
            logging_steps=10,
            eval_strategy="epoch",
            save_strategy="epoch",
            save_total_limit=2,
            seed=ayar.seed,
            report_to=[],
        ),
    )
    egitici.train()
    egitici.save_model(ayar.cikti)

    with open(Path(ayar.cikti) / "egitim_ayari.json", "w", encoding="utf-8") as f:
        json.dump(asdict(ayar), f, ensure_ascii=False, indent=2)

    # Model karti taslagi: hangi veriyle, hangi ayarla, hangi donanimda.
    with open(Path(ayar.cikti) / "MODEL_KARTI.md", "w", encoding="utf-8") as f:
        f.write(
            "# DIVAN-COZ\n\n"
            f"- Taban model: `{ayar.taban_model}`\n"
            f"- Yontem: QLoRA (r={ayar.lora_r}, alpha={ayar.lora_alpha})\n"
            f"- Egitim verisi: `{ayar.veri}`\n"
            f"- Epoch: {ayar.epoch}, lr: {ayar.lr}\n"
            f"- SLURM is kimligi: {os.environ.get('SLURM_JOB_ID', 'yerel kosum')}\n"
            f"- Kume: {os.environ.get('SLURM_JOB_PARTITION', '-')}\n\n"
            "Sinirlar ve bilinen zayifliklar icin bkz. `docs/veri-model-etik.md`.\n"
        )


def main() -> None:
    a = argparse.ArgumentParser(description="DIVAN-COZ QLoRA egitimi")
    varsayilan = EgitimAyari()
    a.add_argument("--taban-model", default=varsayilan.taban_model)
    a.add_argument("--veri", default=varsayilan.veri)
    a.add_argument("--dogrulama", default=varsayilan.dogrulama)
    a.add_argument("--cikti", default=varsayilan.cikti)
    a.add_argument("--epoch", type=int, default=varsayilan.epoch)
    a.add_argument("--lr", type=float, default=varsayilan.lr)
    n = a.parse_args()
    egit(
        EgitimAyari(
            taban_model=n.taban_model,
            veri=n.veri,
            dogrulama=n.dogrulama,
            cikti=n.cikti,
            epoch=n.epoch,
            lr=n.lr,
        )
    )


if __name__ == "__main__":
    main()
