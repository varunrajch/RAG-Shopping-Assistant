"""
config.py
All settings in one place. Change the language model or thresholds here.
"""
import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

# ---------------------------------------------------------------- data
# If the organisers give us data in data/provided we use it, otherwise we use
# the files made by generate_data.py. Both folders use the same file names:
#   catalogue.csv, policy.md, test_questions.json
PROVIDED_DIR = BASE_DIR / "data" / "provided"
GENERATED_DIR = BASE_DIR / "data" / "generated"
DATA_DIR = PROVIDED_DIR if PROVIDED_DIR.exists() else GENERATED_DIR

CATALOGUE_PATH = DATA_DIR / "catalogue.csv"
POLICY_PATH = DATA_DIR / "policy.md"
TEST_QUESTIONS_PATH = DATA_DIR / "test_questions.json"

INDEX_DIR = BASE_DIR / "data" / "index"      # cached embeddings
RESULTS_DIR = BASE_DIR / "results"            # evaluation output
LOG_PATH = BASE_DIR / "logs" / "queries.jsonl"  # one line per query

# ---------------------------------------------------------------- models
# Small sentence transformers model (about 90 MB, runs fine on a laptop CPU).
EMBED_MODEL = "sentence-transformers/all-MiniLM-L6-v2"

# Small instruct model served by Ollama. Use "qwen2.5:3b" for better wording
# (slower). You can also set the LLM_MODEL environment variable.
LLM_MODEL = os.getenv("LLM_MODEL", "qwen2.5:1.5b")
OLLAMA_URL = os.getenv("OLLAMA_URL", "http://localhost:11434")
LLM_TIMEOUT_S = 60
# Set USE_LLM=0 to force template replies (useful for a quick evaluation).
USE_LLM = os.getenv("USE_LLM", "1") != "0"

# ---------------------------------------------------------------- search
W_BM25 = 0.5            # weight of the keyword score in the combined ranking
W_EMB = 0.5             # weight of the embedding (meaning) score
RARE_TOKEN_MAX_DF = 3   # a title word in <= 3 products is a product name ("AeroGlide")

# ---------------------------------------------------------------- decisions
CLEAR_MATCH_MARGIN = 0.15   # top result must beat the 2nd by this much to be "one clear match"
MAX_CLARIFY_OPTIONS = 3     # options listed in a clarifying question
MAX_LIST_ITEMS = 5          # products shown for a list request
LLM_RELEVANCE_MIN = 0.40    # min embedding similarity when the LLM guessed the category
POLICY_MIN_COS = 0.30       # min embedding similarity for a policy section to count
NEAREST_MIN_SIM = 0.45      # min similarity to suggest "the closest thing we sell"

# ---------------------------------------------------------------- demo display
# Pauses used only by the chat window so viewers can follow the steps.
# They are NOT part of the measured latency. Set both to 0 for instant replies.
DEMO_STEP_DELAY_S = 0.45    # pause between pipeline steps in the "Searching..." box
DEMO_WORD_DELAY_S = 0.02    # pause between words while the reply is shown
