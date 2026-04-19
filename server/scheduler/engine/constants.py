"""Scheduling constants and trained-model paths."""
from pathlib import Path

BASE_DIR      = Path(__file__).resolve().parent.parent.parent
TRAINED_DIR   = BASE_DIR / "ml_pipeline" / "trained"
RF_MODEL_PATH = TRAINED_DIR / "rf_model.pkl"
RF_META_PATH  = TRAINED_DIR / "rf_feature_metadata.pkl"
EMBED_PATH    = TRAINED_DIR / "node_embeddings.pkl"

DAYS     = ["MON", "TUE", "WED", "THU", "FRI"]
DAY_FULL = {
    "MON": "Monday", "TUE": "Tuesday", "WED": "Wednesday",
    "THU": "Thursday", "FRI": "Friday", "SAT": "Saturday",
}
TEACHING_SLOTS          = [1, 2, 3, 4, 5, 6]
VALID_CONSECUTIVE_PAIRS = [(1, 2), (2, 3), (3, 4), (5, 6)]
