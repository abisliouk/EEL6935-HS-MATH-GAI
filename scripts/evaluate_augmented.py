import openai
import json
import time
from pathlib import Path

from keys import PREMIUM_API_KEY
from const import *
from utils import safe_parse_json, get_prompt, call_api, evaluate_confidence_accuracy

# Configuration
NUM_SAMPLES = 3  # Set to an integer for testing on fewer samples. None for all.
OUTPUT_FILENAME = "prediction_with_uncertainties_augmented.json"
OUTPUT_PATH = f"{OUTPUT_DIR}/{OUTPUT_FILENAME}"

# OpenAI client
client = openai.OpenAI(api_key=PREMIUM_API_KEY, base_url="http://10.227.119.44:8000/v1")

# Load augmented dataset
with open(INPUT_PATH_AUGMENTED, "r") as f:
    all_data = json.load(f)
    dataset = all_data if NUM_SAMPLES is None else all_data[:NUM_SAMPLES]

results = []

# Inference loop
for idx, item in enumerate(dataset):
    for version_key in ["augmented_1", "augmented_2", "augmented_3"]:
        version = item[version_key]

        question_text = version["question"]
        expected_answer = version["answer"]

        prompt = get_prompt(question_text)
        raw_response = call_api(client, prompt, model=MODEL_LOCAL, idx=idx)

        if not raw_response:
            continue

        parsed = safe_parse_json(raw_response, idx=idx)
        if parsed is None:
            print(f"[Warning @ idx={idx}/{version_key}]: Failed to parse JSON.")
            continue

        predicted = parsed.get("predicted_answer")
        self_conf = float(parsed.get("self_confidence", 0.0))
        internal_conf = float(parsed.get("internal_confidence", 0.0))
        dist = parsed.get("confidence_distribution", {})
        logit_based = dist.get(predicted, 0.0)

        results.append({
            "id": item["id"],
            "question_version": version_key,
            "question": question_text,
            "expected_answer": expected_answer,
            "model_response": {
                "predicted_answer": predicted,
                "confidence": {
                    SELF_EVAL_CONFIDENCE: round(self_conf, 3),
                    LOGIT_BASED_CONFIDENCE: round(logit_based, 3),
                    INTERNAL_BASED_CONFIDENCE: round(internal_conf, 3)
                }
            },
            "raw_text": raw_response,
            "timestamp": time.time()
        })

        # Save incrementally
        Path(OUTPUT_DIR).mkdir(parents=True, exist_ok=True)
        with open(OUTPUT_PATH, "w") as f:
            json.dump(results, f, indent=2)

# Final save
with open(OUTPUT_PATH, "w") as f:
    json.dump(results, f, indent=2)

# Confidence-Accuracy Evaluation
confidence_keys = [
    (SELF_EVAL_CONFIDENCE, "confidence_accuracy_self_eval_augmented.json"),
    (LOGIT_BASED_CONFIDENCE, "confidence_accuracy_logit_augmented.json"),
    (INTERNAL_BASED_CONFIDENCE, "confidence_accuracy_internal_augmented.json")
]

evaluate_confidence_accuracy(results, confidence_keys, output_dir=OUTPUT_DIR)
