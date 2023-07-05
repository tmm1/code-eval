from core.mps_autocast_stub import reassuring_symbol
from core.mpt_device_map import mpt_device_map
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    PreTrainedTokenizer,
    PreTrainedModel,
)
from core import run_eval, fix_indents, replit_glaive_prompt
import os
import torch

# TODO: move to python-dotenv
# add hugging face access token here
TOKEN = ""


@torch.inference_mode()
def generate_batch_completion(
    model: PreTrainedModel, tokenizer: PreTrainedTokenizer, prompt: str, batch_size: int
) -> list[str]:
    prompt_input = replit_glaive_prompt(prompt)
    input_batch = [prompt_input for _ in range(batch_size)]
    inputs = tokenizer(input_batch, return_tensors="pt").to(model.device)
    input_ids_cutoff = inputs.input_ids.size(dim=1)

    generated_ids = model.generate(
        **inputs,
        use_cache=True,
        max_new_tokens=512,
        temperature=0.2,
        top_p=0.95,
        do_sample=True,
        eos_token_id=tokenizer.eos_token_id,
        pad_token_id=tokenizer.pad_token_id,
    )

    batch_completions = tokenizer.batch_decode(
        [ids[input_ids_cutoff:] for ids in generated_ids],
        skip_special_tokens=True,
        clean_up_tokenization_spaces=False,
    )
    torch.mps.empty_cache()

    return [fix_indents(completion) for completion in batch_completions]


if __name__ == "__main__":
    # adjust for n = 10 etc
    num_samples_per_task = 10
    out_path = "results/replit_glaive/eval.jsonl"
    os.makedirs("results/replit_glaive", exist_ok=True)

    tokenizer = AutoTokenizer.from_pretrained(
        "sahil2801/replit-code-instruct-glaive",
        trust_remote_code=True,
        use_auth_token=TOKEN,
    )

    dmap = { key: 'mps' for key in mpt_device_map } if torch.backends.mps.is_available() else mpt_device_map
    model = torch.compile(
        AutoModelForCausalLM.from_pretrained(
            "sahil2801/replit-code-instruct-glaive",
            torch_dtype=torch.float16 if torch.backends.mps.is_available() else torch.bfloat16,
            device_map=dmap,
            trust_remote_code=True,
            use_auth_token=TOKEN,
            init_device="meta",
        ).eval()
    )

    run_eval(
        model, tokenizer, num_samples_per_task, out_path, generate_batch_completion
    )
