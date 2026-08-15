"""
NyayaVaani RAG Evaluation Script (Langfuse SDK v4.x)
----------------------------------------------------
Runs the RAG pipeline against a Langfuse dataset using native run_experiment.

Usage:
    $env:PYTHONPATH="."
    python eval/run_dataset_eval.py
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv(override=True)

from langfuse import Langfuse
from src.rag.retriever import get_rag

DATASET_NAME = "nyayavaani-rag-eval"
RUN_NAME = "rag-pipeline-v4"

print("Initializing Langfuse and RAG pipeline...")
langfuse = Langfuse()
rag = get_rag()
print("Ready.\n")

try:
    dataset = langfuse.get_dataset(DATASET_NAME)
    print(f"Loaded dataset: '{DATASET_NAME}' - {len(dataset.items)} test items\n")
except Exception as e:
    print(f"Could not load dataset '{DATASET_NAME}': {e}")
    sys.exit(1)

def rag_task(*, item, **kwargs):
    if isinstance(item.input, str):
        question = item.input
    elif isinstance(item.input, dict):
        question = item.input.get("question", item.input.get("input", str(item.input)))
    else:
        question = str(item.input)
    
    question = question.strip().strip('"').strip("'")
    print(f"Processing: {question[:65]}...")
    
    result = rag.answer_question(question)
    answer = result.get("answer", "")
    chunks = result.get("chunks", [])
    context = result.get("context", "")
    if not context and chunks:
        context = "\n\n".join([
            f"[Source: {c.get('source','?')} | Page {c.get('page','?')}]\n{c['content']}"
            for c in chunks
        ])
    
    return {
        "answer": answer,
        "context": context,
        "sources": list({c.get("source", "") for c in chunks if c.get("source")})
    }

print(f"Running experiment '{RUN_NAME}' on {len(dataset.items)} items...")
exp_result = langfuse.run_experiment(
    name=DATASET_NAME,
    run_name=RUN_NAME,
    data=dataset.items,
    task=rag_task,
    max_concurrency=2
)

print("\n" + "="*60)
print(f"[SUCCESS] Experiment completed: {exp_result.run_name}")
print(f"   Items processed : {len(exp_result.item_results)}")
print("   Check results at: http://localhost:3000 -> Datasets -> nyayavaani-rag-eval -> Runs")
print("="*60)

langfuse.flush()
