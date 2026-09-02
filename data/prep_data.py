"""
Prep script — reads the raw SPSS (.sav) export for the LEP 911 dispatch study
and writes a clean, de-identified data/calls.csv for the Streamlit app.

Usage:
    python data/prep_data.py [path/to/file.sav]

If no path is given, defaults to data/Hafsah_Dataset_7_29_26.sav.
"""

import sys
from pathlib import Path

import pandas as pd
import pyreadstat

DATA_DIR = Path(__file__).resolve().parent
DEFAULT_SAV = DATA_DIR / "Hafsah_Dataset_7_29_26.sav"
OUTPUT_CSV = DATA_DIR / "calls.csv"

CALL_CENTER_MAP = {1: "Valley", 2: "NORCOM", 3: "Verdugo", 4: "Benton/Franklin"}
YES_NO_MAP = {0: "No", 1: "Yes"}
LANG_GROUP_MAP = {0: "Unknown", 1: "Spanish", 2: "High-frequency", 3: "Low-frequency"}
COMPLIANCE_MAP = {0: "No compliance", 1: "Compliance"}
JARGON_VALIDATION_MAP = {0: "No validation", 1: "Validated with jargon", 2: "Validated without jargon"}
EMOTION_MAP = {0: "None", 1: "Some", 2: "A lot"}
EMERGENCY_TYPE_MAP = {
    0: "Respiratory distress",
    1: "Cardiac complaint",
    2: "Cardiac arrest",
    3: "Consciousness",
    4: "Pain, bleeding, or reduced mobility",
    5: "Traumatic injury or toxic exposure",
    6: "No or limited information available",
}

TIME_OF_DAY_BINS = [-1, 5, 11, 17, 20, 23]
TIME_OF_DAY_LABELS = [
    "Overnight (12-6a)",
    "Morning (6a-12p)",
    "Afternoon (12-6p)",
    "Evening (6-9p)",
    "Late Night (9p-12a)",
]


def blank_to_null(series):
    return series.replace("", pd.NA)


def prep(sav_path: Path) -> pd.DataFrame:
    raw, _meta = pyreadstat.read_sav(str(sav_path))

    out = pd.DataFrame()
    out["call_id"] = raw["event"]
    out["call_center"] = raw["com"].map(CALL_CENTER_MAP)

    call_date = raw["date"]
    out["call_date"] = call_date.where(call_date.dt.year != 1899)

    hour = raw["start_ts"].dt.hour
    out["time_of_day"] = pd.cut(
        hour, bins=TIME_OF_DAY_BINS, labels=TIME_OF_DAY_LABELS
    )

    out["interpreter_used"] = raw["langline"].map(YES_NO_MAP)
    out["lang_group"] = raw["lang_group"].map(LANG_GROUP_MAP)
    out["language"] = blank_to_null(raw["language"]).str.title()
    out["zip_code"] = blank_to_null(raw["zip_code"]).astype("string")

    out["interpreter_connect_min"] = raw["tbtwnm_opiconacc"]
    out["response_time_min"] = raw["ttom_dispatch_fix_na"]
    out["onscene_time_min"] = raw["ttom_onscene_fix"]

    out["hangup"] = raw["hangup"].map(YES_NO_MAP)
    out["compliance"] = raw["compliance_bin"].map(COMPLIANCE_MAP)
    out["jargon_validation"] = raw["needval_cr"].map(JARGON_VALIDATION_MAP)
    out["caller_emotion"] = raw["highemo_rp"].map(EMOTION_MAP)
    out["calltaker_emotion"] = raw["highemo_cr"].map(EMOTION_MAP)
    out["repetition_used"] = raw["repeat_cr"].map(YES_NO_MAP)
    out["rephrasing_used"] = raw["rephrase_cr"].map(YES_NO_MAP)
    out["emotion_validated"] = raw["emoval_cr"].map(YES_NO_MAP)
    out["emergency_type"] = raw["idc2_new"].map(EMERGENCY_TYPE_MAP)

    return out


def main():
    sav_path = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SAV
    if not sav_path.exists():
        sys.exit(f"SPSS file not found: {sav_path}")

    df = prep(sav_path)
    df.to_csv(OUTPUT_CSV, index=False)
    print(f"Wrote {len(df):,} rows to {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
