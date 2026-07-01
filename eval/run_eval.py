import json
import logging
import requests
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

API_URL = "http://localhost:8000/chat"
TRACES_FILE = Path(__file__).parent.parent / "data" / "evaluation_traces.json"

def calculate_recall_at_k(recommended_names, expected_names, k=3):
    """Calculate Recall@K for a single query."""
    if not expected_names:
        return 1.0
        
    top_k_recommended = recommended_names[:k]
    hits = sum(1 for name in expected_names if name in top_k_recommended)
    return hits / len(expected_names)

def run_evaluation():
    if not TRACES_FILE.exists():
        logging.error(f"Traces file not found: {TRACES_FILE}. Run generate_mock_traces.py first.")
        return

    with open(TRACES_FILE, "r", encoding="utf-8") as f:
        traces = json.load(f)

    logging.info(f"Starting evaluation on {len(traces)} traces...")
    
    total_recall = 0.0
    
    for trace in traces:
        logging.info(f"\n--- Testing Trace: {trace['id']} ---")
        logging.info(f"Query: {trace['query']}")
        logging.info(f"Expected: {trace['expected_shortlist']}")
        
        # Call the API
        payload = {
            "messages": [
                {"role": "user", "content": trace["query"]}
            ]
        }
        
        try:
            response = requests.post(API_URL, json=payload, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            recommended_names = [rec["name"] for rec in data.get("recommendations", [])]
            logging.info(f"Agent Recommended: {recommended_names}")
            
            # Calculate metrics
            recall = calculate_recall_at_k(recommended_names, trace["expected_shortlist"], k=3)
            total_recall += recall
            logging.info(f"Recall@3: {recall:.2f}")
            
        except requests.exceptions.ConnectionError:
            logging.error("Failed to connect to API. Is the FastAPI server running?")
            return
        except Exception as e:
            logging.error(f"Error calling API: {e}")
            
    # Final Score
    mean_recall = total_recall / len(traces)
    logging.info(f"\n{'='*30}")
    logging.info(f"EVALUATION COMPLETE")
    logging.info(f"Mean Recall@3: {mean_recall:.2f}")
    logging.info(f"{'='*30}")

if __name__ == "__main__":
    run_evaluation()
