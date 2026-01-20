from transformers.pipelines import pipeline

import torch

# Load the 4B Multimodal variant
model_id = "google/medgemma-1.5-4b-it"

pipe = pipeline(
    "text-generation",
    model=model_id,
    device_map="auto",
    torch_dtype=torch.bfloat16
)

# Initial Test Query
messages = [
    {"role": "user", "content": "Explain the significance of a Creatinine level of 2.1 mg/dL in an elderly patient."}
]

output = pipe(messages, max_new_tokens=256)
print(output[0]['generated_text'][-1]['content'])
