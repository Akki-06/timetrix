"""
TIMETRIX — Graph Builder
=========================
Builds a heterogeneous NetworkX graph from the 4 clean CSVs.

Node types  : faculty, course, section, room, timeslot
Edge types  : teaches, belongs_to, scheduled_at, uses, occupied_at

Input  CSVs : timetable_dataset_clean.csv
              faculty_metadata.csv
              rooms.csv
              timeslots.csv

Output files: timetrix_graph.gpickle   — full NetworkX graph
              node_features.pkl        — {node_id: feature_vector}
              node_metadata.pkl        — {node_id: human-readable info}
              graph_stats.json         — summary for validation

Run:
    python ml_pipeline/graph_builder.py
"""

import os
import json
import pickle
import logging
import numpy as np
import pandas as pd
import networkx as nx
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS  — relative to server/ directory
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR    = Path(__file__).resolve().parent.parent   # timetrix/server/
DATA_DIR    = BASE_DIR / "ml_pipeline" / "data"
OUTPUT_DIR  = BASE_DIR / "ml_pipeline" / "trained"

SESSION_CSV  = DATA_DIR / "timetable_dataset.csv"
FACULTY_CSV  = DATA_DIR / "faculty_metadata.csv"
ROOMS_CSV    = DATA_DIR / "rooms.csv"
SLOTS_CSV    = DATA_DIR / "timeslots.csv"

OUTPUT_GRAPH    = OUTPUT_DIR / "timetrix_graph.gpickle"
OUTPUT_FEATURES = OUTPUT_DIR / "node_features.pkl"
OUTPUT_META     = OUTPUT_DIR / "node_metadata.pkl"
OUTPUT_STATS    = OUTPUT_DIR / "graph_stats.json"


# ─────────────────────────────────────────────────────────────────────────────
# NODE ID CONVENTIONS
# Every node has a globally unique string ID with a type prefix.
# This avoids any collision between e.g. a room "1112" and a course code "1112".
#
#   faculty   → "FAC::<name>"          e.g. "FAC::Mr. Rahul Bhatt"
#   course    → "CRS::<name>"          e.g. "CRS::Database Management Systems"
#   section   → "SEC::<prog>_<sem>_<sec>" e.g. "SEC::BTech CSE_4_A"
#   room      → "RRM::<room_id>"       e.g. "RRM::1118"
#   timeslot  → "TSL::<timeslot_id>"   e.g. "TSL::MON_S2"
# ─────────────────────────────────────────────────────────────────────────────

def fac_id(name):    return f"FAC::{name.strip()}"
def crs_id(name):    return f"CRS::{name.strip()}"
def sec_id(p,s,sec): return f"SEC::{p.strip()}_{s}_{sec.strip()}"
def rm_id(room):     return f"RRM::{str(room).strip()}"
def ts_id(tid):      return f"TSL::{tid.strip()}"


# ─────────────────────────────────────────────────────────────────────────────
# FEATURE VECTOR BUILDERS
# All vectors are fixed-length floats. Same meaning for same position always.
# ─────────────────────────────────────────────────────────────────────────────

def faculty_features(row):
    """8-dim feature vector for a faculty node."""
    desig_enc = {
        "Visiting": 0.0, "Assistant Professor": 0.2,
        "Associate Professor": 0.6, "Professor": 0.8,
        "HOD": 0.9, "Dean": 1.0
    }
    emp_enc = {"Visiting": 0.0, "Part Time": 0.5, "Full Time": 1.0}

    return np.array([
        desig_enc.get(str(row.get("designation","")), 0.2),
        float(row.get("max_hours_per_week", 18)) / 18.0,
        float(row.get("teaches_theory", 1)),
        float(row.get("teaches_lab", 0)),
        min(float(row.get("num_unique_courses", 1)) / 10.0, 1.0),
        min(float(row.get("num_programs_taught", 1)) / 4.0, 1.0),
        emp_enc.get(str(row.get("employment_type","")), 1.0),
        float(row.get("is_hod", 0)) * 0.5 + float(row.get("is_dean", 0)),
    ], dtype=np.float32)


def course_features(row):
    """7-dim feature vector for a course node."""
    type_enc = {"theory": 0.0, "lab": 1.0}
    prog_enc = {"BTech CSE": 0.0, "BCA": 0.25, "BSc IT": 0.5,
                "MCA": 0.75, "Poly CSE": 1.0}

    return np.array([
        type_enc.get(str(row.get("session_type","theory")), 0.0),
        min(float(row.get("contact_hours_weekly", 3)) / 8.0, 1.0),
        float(row.get("is_lab", 0)),
        float(row.get("is_elective_split", 0)),
        float(row.get("semester_int", 1)) / 8.0,
        prog_enc.get(str(row.get("program","")), 0.0),
        float(row.get("is_consecutive_lab", 0)),
    ], dtype=np.float32)


def section_features(row):
    """5-dim feature vector for a section node."""
    prog_enc = {"BTech CSE": 0.0, "BCA": 0.25, "BSc IT": 0.5,
                "MCA": 0.75, "Poly CSE": 1.0}

    return np.array([
        prog_enc.get(str(row.get("program","")), 0.0),
        float(row.get("semester_int", 1)) / 8.0,
        float(row.get("section_encoded", 0)) / 5.0,
        float(row.get("semester_type_enc", 0)),   # 0=even, 1=odd
        0.5,   # placeholder for section strength (not in data)
    ], dtype=np.float32)


def room_features(row):
    """6-dim feature vector for a room node."""
    type_enc = {"theory": 0.0, "lab": 1.0, "seminar": 0.5}
    lab_enc  = {"": 0.0, "general_computing": 0.25, "networking": 0.5,
                "digital_electronics": 0.75, "software": 1.0}

    return np.array([
        float(row.get("is_lab", 0)),
        float(row.get("capacity", 60)) / 120.0,
        float(row.get("floor_norm", 0.25)),
        type_enc.get(str(row.get("room_type","theory")), 0.0),
        lab_enc.get(str(row.get("lab_type","")), 0.0),
        float(row.get("is_shared", 1)),
    ], dtype=np.float32)


def timeslot_features(row):
    """6-dim feature vector for a timeslot node."""
    return np.array([
        float(row.get("day_index", 0)) / 4.0,
        float(row.get("slot_index", 1)) / 6.0,
        float(row.get("is_morning", 0)),
        float(row.get("is_post_lunch", 0)),
        float(row.get("is_pre_lunch", 0)),
        float(row.get("is_first_slot", 0)) * 0.5 +
        float(row.get("is_last_slot", 0)),
    ], dtype=np.float32)


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH BUILDER
# ─────────────────────────────────────────────────────────────────────────────

def build_graph(sessions, faculty_df, rooms_df, slots_df):
    """
    Builds heterogeneous directed graph.
    Nodes carry: type, features, label (human-readable name)
    Edges carry: weight (frequency count), relation type
    """
    G = nx.DiGraph()

    node_features = {}   # node_id → np.array
    node_meta     = {}   # node_id → dict with human info

    # ── Index lookup tables ───────────────────────────────────────────────────
    fac_lookup  = {r["faculty_name"]: r for _, r in faculty_df.iterrows()}
    room_lookup = {str(r["room_id"]): r for _, r in rooms_df.iterrows()}

    # Build timeslot lookup: (day, slot_index) → row
    slot_lookup = {}
    for _, r in slots_df[slots_df["is_lunch"] == 0].iterrows():
        slot_lookup[(r["day"], int(r["slot_index"]))] = r

    # ── PASS 1: Add all nodes ─────────────────────────────────────────────────
    log.info("Pass 1: Building nodes...")

    faculty_seen  = set()
    course_seen   = set()
    section_seen  = set()
    room_seen     = set()
    timeslot_seen = set()

    for _, row in sessions.iterrows():
        # ── Faculty node ──────────────────────────────────────────────────────
        fac = str(row["faculty"]).strip()
        if fac and fac != "TBD" and fac not in faculty_seen:
            nid  = fac_id(fac)
            fmeta = fac_lookup.get(fac, {})
            feat  = faculty_features(fmeta)
            G.add_node(nid, node_type="faculty",   label=fac)
            node_features[nid] = feat
            node_meta[nid] = {
                "type"        : "faculty",
                "name"        : fac,
                "designation" : fmeta.get("designation","Assistant Professor"),
                "department"  : fmeta.get("department","Computer Science"),
                "max_hours"   : fmeta.get("max_hours_per_week", 18),
            }
            faculty_seen.add(fac)

        # ── Course node ───────────────────────────────────────────────────────
        cname = str(row["course_name"]).strip()
        if cname and cname not in course_seen:
            nid  = crs_id(cname)
            feat = course_features(row)
            G.add_node(nid, node_type="course", label=cname)
            node_features[nid] = feat
            node_meta[nid] = {
                "type"         : "course",
                "name"         : cname,
                "session_type" : row["session_type"],
                "is_lab"       : int(row["is_lab"]),
                "course_code"  : str(row.get("course_code","")).strip(),
            }
            course_seen.add(cname)

        # ── Section node ──────────────────────────────────────────────────────
        prog = str(row["program"]).strip()
        sem  = str(row["semester"]).strip()
        sec  = str(row["section"]).strip()
        sid  = sec_id(prog, sem, sec)
        if sid not in section_seen:
            sem_type_enc = 1.0 if row["semester_type"] == "odd" else 0.0
            row_copy = dict(row)
            row_copy["semester_type_enc"] = sem_type_enc
            feat = section_features(row_copy)
            label = f"{prog} Sem{sem} {sec}"
            G.add_node(sid, node_type="section", label=label)
            node_features[sid] = feat
            node_meta[sid] = {
                "type"          : "section",
                "program"       : prog,
                "semester"      : sem,
                "section"       : sec,
                "semester_type" : row["semester_type"],
                "academic_year" : row["academic_year"],
            }
            section_seen.add(sid)

        # ── Room node ─────────────────────────────────────────────────────────
        room = str(row["room"]).strip()
        if room and room not in room_seen:
            nid    = rm_id(room)
            rmeta  = room_lookup.get(room, {})
            feat   = room_features(rmeta)
            G.add_node(nid, node_type="room", label=room)
            node_features[nid] = feat
            node_meta[nid] = {
                "type"      : "room",
                "room_id"   : room,
                "is_lab"    : int(rmeta.get("is_lab", 0)),
                "capacity"  : int(rmeta.get("capacity", 60)),
                "building"  : str(rmeta.get("building","Unknown")),
            }
            room_seen.add(room)

        # ── Timeslot node ─────────────────────────────────────────────────────
        day      = str(row["day"]).strip()
        slot_idx = int(row["slot_index"])
        ts_key   = (day, slot_idx)
        ts_nid   = ts_id(f"{day[:3].upper()}_S{slot_idx}")
        if ts_nid not in timeslot_seen:
            slot_row = slot_lookup.get(ts_key, None)
            if slot_row is not None:
                feat       = timeslot_features(slot_row)
                start_time = str(slot_row.get("start_time",""))
                end_time   = str(slot_row.get("end_time",""))
            else:
                feat = timeslot_features({
                    "day_index"    : row["day_index"],
                    "slot_index"   : slot_idx,
                    "is_morning"   : 1 if slot_idx <= 3 else 0,
                    "is_post_lunch": 1 if slot_idx >= 5 else 0,
                    "is_pre_lunch" : 1 if slot_idx == 4 else 0,
                    "is_first_slot": 1 if slot_idx == 1 else 0,
                    "is_last_slot" : 1 if slot_idx == 6 else 0,
                })
                start_time = ""
                end_time   = ""
            G.add_node(ts_nid, node_type="timeslot", label=f"{day} Slot {slot_idx}")
            node_features[ts_nid] = feat
            node_meta[ts_nid] = {
                "type"       : "timeslot",
                "day"        : day,
                "slot_index" : slot_idx,
                "start_time" : start_time,
                "end_time"   : end_time,
            }
            timeslot_seen.add(ts_nid)

    log.info(f"  Faculty nodes  : {len(faculty_seen)}")
    log.info(f"  Course nodes   : {len(course_seen)}")
    log.info(f"  Section nodes  : {len(section_seen)}")
    log.info(f"  Room nodes     : {len(room_seen)}")
    log.info(f"  Timeslot nodes : {len(timeslot_seen)}")

    # ── PASS 2: Add edges ─────────────────────────────────────────────────────
    log.info("Pass 2: Building edges...")

    # Edge weight counters — accumulate frequency
    edge_weights = {}

    def add_edge(src, dst, rel):
        key = (src, dst, rel)
        edge_weights[key] = edge_weights.get(key, 0) + 1

    for _, row in sessions.iterrows():
        fac   = str(row["faculty"]).strip()
        cname = str(row["course_name"]).strip()
        prog  = str(row["program"]).strip()
        sem   = str(row["semester"]).strip()
        sec   = str(row["section"]).strip()
        room  = str(row["room"]).strip()
        day   = str(row["day"]).strip()
        slot  = int(row["slot_index"])

        crs_nid = crs_id(cname)
        sec_nid = sec_id(prog, sem, sec)
        rm_nid  = rm_id(room)
        ts_nid  = ts_id(f"{day[:3].upper()}_S{slot}")

        # Edge: Faculty --teaches--> Course
        if fac and fac != "TBD":
            add_edge(fac_id(fac), crs_nid, "teaches")

        # Edge: Course --belongs_to--> Section
        add_edge(crs_nid, sec_nid, "belongs_to")

        # Edge: Section --scheduled_at--> Timeslot
        add_edge(sec_nid, ts_nid, "scheduled_at")

        # Edge: Section --uses--> Room
        add_edge(sec_nid, rm_nid, "uses")

        # Edge: Faculty --occupied_at--> Timeslot
        if fac and fac != "TBD":
            add_edge(fac_id(fac), ts_nid, "occupied_at")

        # Edge: Room --used_at--> Timeslot
        add_edge(rm_nid, ts_nid, "used_at")

        # Edge: Faculty --teaches_in--> Room  (faculty-room affinity)
        if fac and fac != "TBD":
            add_edge(fac_id(fac), rm_nid, "teaches_in")

    # Commit edges with weights
    for (src, dst, rel), weight in edge_weights.items():
        if G.has_node(src) and G.has_node(dst):
            G.add_edge(src, dst, relation=rel, weight=weight)

    log.info(f"  Total edges    : {G.number_of_edges()}")

    return G, node_features, node_meta


# ─────────────────────────────────────────────────────────────────────────────
# VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_graph(G, node_features):
    log.info("Validating graph...")

    errors   = []
    warnings = []

    # Every node must have a feature vector
    nodes_without_features = [n for n in G.nodes if n not in node_features]
    if nodes_without_features:
        errors.append(f"{len(nodes_without_features)} nodes missing feature vectors")

    # Feature vectors must be the right length
    expected_dims = {
        "faculty": 8, "course": 7, "section": 5,
        "room": 6, "timeslot": 6
    }
    dim_errors = 0
    for nid, feat in node_features.items():
        ntype = G.nodes[nid].get("node_type","")
        exp   = expected_dims.get(ntype, -1)
        if exp > 0 and len(feat) != exp:
            dim_errors += 1
    if dim_errors:
        errors.append(f"{dim_errors} nodes have wrong feature vector length")

    # No NaN or Inf in any feature vector
    bad_features = sum(
        1 for f in node_features.values()
        if np.any(np.isnan(f)) or np.any(np.isinf(f))
    )
    if bad_features:
        errors.append(f"{bad_features} nodes have NaN/Inf in features")

    # Every faculty node must have at least one 'teaches' edge
    fac_nodes = [n for n, d in G.nodes(data=True) if d.get("node_type")=="faculty"]
    fac_no_edges = [n for n in fac_nodes if G.out_degree(n) == 0]
    if fac_no_edges:
        warnings.append(f"{len(fac_no_edges)} faculty nodes have no outgoing edges")

    # Graph should be connected (weakly)
    undirected = G.to_undirected()
    components = nx.number_connected_components(undirected)
    if components > 1:
        warnings.append(f"Graph has {components} connected components (expected 1)")

    return errors, warnings


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # ── Load CSVs ─────────────────────────────────────────────────────────────
    log.info("Loading CSVs...")
    sessions   = pd.read_csv(SESSION_CSV)
    faculty_df = pd.read_csv(FACULTY_CSV)
    rooms_df   = pd.read_csv(ROOMS_CSV)
    slots_df   = pd.read_csv(SLOTS_CSV)

    # Fill any remaining empty strings defensively
    sessions["course_code"] = sessions["course_code"].fillna("")
    rooms_df["lab_type"]    = rooms_df["lab_type"].fillna("")

    log.info(f"  Sessions  : {len(sessions)} rows")
    log.info(f"  Faculty   : {len(faculty_df)} rows")
    log.info(f"  Rooms     : {len(rooms_df)} rows")
    log.info(f"  Timeslots : {len(slots_df)} rows")

    # ── Build graph ───────────────────────────────────────────────────────────
    log.info("Building graph...")
    G, node_features, node_meta = build_graph(
        sessions, faculty_df, rooms_df, slots_df
    )

    # ── Validate ──────────────────────────────────────────────────────────────
    errors, warnings = validate_graph(G, node_features)
    for e in errors:   log.error(f"  ERROR: {e}")
    for w in warnings: log.warning(f"  WARN:  {w}")
    if errors:
        raise RuntimeError(f"Graph validation failed with {len(errors)} error(s)")

    # ── Stats ─────────────────────────────────────────────────────────────────
    node_type_counts = {}
    for n, d in G.nodes(data=True):
        t = d.get("node_type", "unknown")
        node_type_counts[t] = node_type_counts.get(t, 0) + 1

    edge_type_counts = {}
    for u, v, d in G.edges(data=True):
        r = d.get("relation","unknown")
        edge_type_counts[r] = edge_type_counts.get(r, 0) + 1

    stats = {
        "total_nodes"      : G.number_of_nodes(),
        "total_edges"      : G.number_of_edges(),
        "node_types"       : node_type_counts,
        "edge_types"       : edge_type_counts,
        "is_directed"      : True,
        "avg_degree"       : round(
            sum(d for _, d in G.degree()) / G.number_of_nodes(), 2
        ),
        "sessions_used"    : len(sessions),
        "validation_errors": len(errors),
        "validation_warns" : len(warnings),
    }

    log.info("Graph stats:")
    log.info(f"  Total nodes : {stats['total_nodes']}")
    log.info(f"  Total edges : {stats['total_edges']}")
    log.info(f"  Node types  : {stats['node_types']}")
    log.info(f"  Edge types  : {stats['edge_types']}")
    log.info(f"  Avg degree  : {stats['avg_degree']}")

    # ── Save ──────────────────────────────────────────────────────────────────
    log.info("Saving outputs...")

    # Graph
    with open(OUTPUT_GRAPH, "wb") as f:
        pickle.dump(G, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Node features
    with open(OUTPUT_FEATURES, "wb") as f:
        pickle.dump(node_features, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Node metadata
    with open(OUTPUT_META, "wb") as f:
        pickle.dump(node_meta, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Stats
    with open(OUTPUT_STATS, "w") as f:
        json.dump(stats, f, indent=2)

    log.info(f"  Graph    → {OUTPUT_GRAPH}")
    log.info(f"  Features → {OUTPUT_FEATURES}")
    log.info(f"  Metadata → {OUTPUT_META}")
    log.info(f"  Stats    → {OUTPUT_STATS}")
    log.info("Done.")

    return G, node_features, node_meta, stats


if __name__ == "__main__":
    main()
