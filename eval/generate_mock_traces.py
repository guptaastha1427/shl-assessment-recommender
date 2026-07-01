import json
from pathlib import Path
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# This matches the sample data in our mock scraper
TRACES = [
    {
        "id": "trace_001",
        "persona": "Hiring Manager",
        "query": "I am hiring a software engineer and I need a technical assessment to test their Java skills.",
        "fact_set": {
            "role": "Software Engineer",
            "skills": ["Java"],
            "remote": True
        },
        "expected_shortlist": ["Java 8 (New)"]
    },
    {
        "id": "trace_002",
        "persona": "HR Professional",
        "query": "We are hiring for a leadership position. I need an assessment to evaluate their workplace behavior and personality traits.",
        "fact_set": {
            "role": "Leadership",
            "test_type": "Personality & Behaviour"
        },
        "expected_shortlist": ["OPQ32r"]
    },
    {
        "id": "trace_003",
        "persona": "Recruiter",
        "query": "I need a general cognitive ability test that includes numerical and inductive reasoning. It needs to be under 40 minutes.",
        "fact_set": {
            "test_type": "Cognitive Ability",
            "max_duration": 40
        },
        "expected_shortlist": ["Verify G+ (General Ability)"]
    }
]

def generate_traces():
    output_dir = Path(__file__).parent.parent / "data"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    file_path = output_dir / "evaluation_traces.json"
    
    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(TRACES, f, indent=2)
        
    logger.info(f"Generated {len(TRACES)} mock evaluation traces at {file_path}")

if __name__ == "__main__":
    generate_traces()
