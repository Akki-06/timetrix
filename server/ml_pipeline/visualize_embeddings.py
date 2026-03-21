"""
TIMETRIX — Complete Visualization Suite
=========================================
Generates three separate PNG files, one per layer of the system:

  viz_01_graph.png  — The knowledge graph: subgraph, node/edge distributions,
                      degree histogram, edge-weight heatmap
  viz_02_gnn.png    — GNN embeddings: t-SNE (all nodes), t-SNE (faculty),
                      PCA scree plot, cosine-similarity heatmap by node type
  viz_03_rf.png     — Random Forest ensemble: feature importances, class score
                      distributions, Precision-Recall curve with threshold,
                      calibration (reliability) diagram

Run from server/:
    py ml_pipeline/visualize_embeddings.py
"""

import os, sys, json, pickle, warnings
from collections import defaultdict
from pathlib import Path

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import matplotlib.gridspec as gridspec
from matplotlib.colors import LinearSegmentedColormap
import networkx as nx
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
from sklearn.metrics import precision_recall_curve, auc
from sklearn.calibration import calibration_curve
import pandas as pd

warnings.filterwarnings("ignore")

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR  = Path(__file__).resolve().parent          # ml_pipeline/
TRAIN_DIR = BASE_DIR / "trained"
DATA_DIR  = BASE_DIR / "data"

GRAPH_PATH    = TRAIN_DIR / "timetrix_graph.gpickle"
EMBED_PATH    = TRAIN_DIR / "node_embeddings.pkl"
META_PATH     = TRAIN_DIR / "node_metadata.pkl"
RF_MODEL_PATH = TRAIN_DIR / "rf_model.pkl"
RF_META_PATH  = TRAIN_DIR / "rf_feature_metadata.pkl"
RF_REPORT     = TRAIN_DIR / "rf_training_report.json"

SESSION_CSV = DATA_DIR / "timetable_dataset.csv"
FACULTY_CSV = DATA_DIR / "faculty_metadata.csv"
ROOMS_CSV   = DATA_DIR / "rooms.csv"

OUT_GRAPH = TRAIN_DIR / "viz_01_graph.png"
OUT_GNN   = TRAIN_DIR / "viz_02_gnn.png"
OUT_RF    = TRAIN_DIR / "viz_03_rf.png"

# ─────────────────────────────────────────────────────────────────────────────
# SHARED STYLE
# ─────────────────────────────────────────────────────────────────────────────

BG      = "#0F1117"
PANEL   = "#1A1D27"
GRID    = "#2A2D3A"
TEXT    = "#E0E0E0"
SUBTLE  = "#888888"

TYPE_COLORS = {
    "faculty"  : "#E74C3C",
    "course"   : "#3498DB",
    "section"  : "#2ECC71",
    "room"     : "#F39C12",
    "timeslot" : "#9B59B6",
}

def style_ax(ax, title="", xlabel="", ylabel=""):
    ax.set_facecolor(PANEL)
    ax.tick_params(colors=SUBTLE, labelsize=8)
    for s in ax.spines.values():
        s.set_edgecolor(GRID)
    ax.xaxis.label.set_color(SUBTLE)
    ax.yaxis.label.set_color(SUBTLE)
    if title:
        ax.set_title(title, color=TEXT, fontsize=10, pad=8)
    if xlabel:
        ax.set_xlabel(xlabel, color=SUBTLE, fontsize=8)
    if ylabel:
        ax.set_ylabel(ylabel, color=SUBTLE, fontsize=8)
    ax.grid(color=GRID, linewidth=0.5, alpha=0.6)

def new_fig(rows, cols, title, figsize):
    fig = plt.figure(figsize=figsize)
    fig.patch.set_facecolor(BG)
    fig.suptitle(title, color=TEXT, fontsize=14, fontweight="bold", y=0.98)
    return fig

# ─────────────────────────────────────────────────────────────────────────────
# LOAD SHARED ARTIFACTS
# ─────────────────────────────────────────────────────────────────────────────

print("Loading artifacts...")
with open(GRAPH_PATH, "rb") as f:   G          = pickle.load(f)
with open(EMBED_PATH,  "rb") as f:  embeddings = pickle.load(f)
with open(META_PATH,   "rb") as f:  node_meta  = pickle.load(f)

all_ids    = [n for n in G.nodes() if n in embeddings]
node_types = [G.nodes[n].get("node_type", "?") for n in all_ids]
embed_mat  = np.array([embeddings[n] for n in all_ids])
print(f"  Nodes with embeddings : {len(all_ids)}")
print(f"  Embedding shape       : {embed_mat.shape}")


# ========================================================================
# FIGURE 1 — GRAPH STRUCTURE
# 4 panels: subgraph | node-type bar | edge-type bar | degree histogram
# ========================================================================

print("\nBuilding Figure 1 — Graph Structure...")

fig1 = new_fig(2, 2, "TIMETRIX — Knowledge Graph Structure", (22, 14))
gs   = gridspec.GridSpec(2, 2, figure=fig1, hspace=0.38, wspace=0.32)

# ── Panel 1-A: Subgraph (sections + 1-hop) ───────────────────────────────────
ax_sg = fig1.add_subplot(gs[0, 0])
ax_sg.set_facecolor(PANEL)
ax_sg.set_title("Schedule Subgraph\n(3 sections + 1-hop neighbours)",
                color=TEXT, fontsize=10, pad=8)

target_sections = []
for n, d in G.nodes(data=True):
    if d.get("node_type") == "section":
        lbl = d.get("label", "")
        if "4" in lbl and any(x in lbl for x in ("Sem4 A", "Sem4 B", "Sem4 C",
                                                   "S4 A",   "S4 B",   "S4 C")):
            target_sections.append(n)
        if len(target_sections) == 3:
            break
if not target_sections:
    target_sections = [n for n, d in G.nodes(data=True)
                       if d.get("node_type") == "section"][:3]

subgraph_nodes = set(target_sections)
for s in target_sections:
    out_edges = sorted(G.out_edges(s, data=True),
                       key=lambda e: e[2].get("weight", 1), reverse=True)[:7]
    in_edges  = sorted(G.in_edges(s, data=True),
                       key=lambda e: e[2].get("weight", 1), reverse=True)[:3]
    subgraph_nodes.update([v for _, v, _ in out_edges])
    subgraph_nodes.update([u for u, _, _ in in_edges])

SG  = G.subgraph(subgraph_nodes).copy()
pos = nx.spring_layout(SG, seed=7, k=3.0, iterations=100)

EDGE_COLORS = {
    "teaches"     : "#E74C3C", "scheduled_at": "#9B59B6",
    "uses"        : "#F39C12", "belongs_to"  : "#3498DB",
    "occupied_at" : "#2ECC71", "used_at"     : "#666666",
    "teaches_in"  : "#E67E22",
}
for rel, ecol in EDGE_COLORS.items():
    edges = [(u, v) for u, v, d in SG.edges(data=True) if d.get("relation") == rel]
    if edges:
        nx.draw_networkx_edges(SG, pos, edgelist=edges, edge_color=ecol,
                               alpha=0.55, width=1.2, arrows=True, arrowsize=8,
                               connectionstyle="arc3,rad=0.12", ax=ax_sg)
for ntype, color in TYPE_COLORS.items():
    ns = [n for n in SG.nodes() if G.nodes[n].get("node_type") == ntype]
    if ns:
        sizes = [550 if n in target_sections else 200 for n in ns]
        nx.draw_networkx_nodes(SG, pos, nodelist=ns, node_color=color,
                               node_size=sizes, alpha=0.92, ax=ax_sg)

labels_sg = {}
for n in SG.nodes():
    lbl   = G.nodes[n].get("label", "")
    ntype = G.nodes[n].get("node_type", "")
    if ntype == "faculty":
        p = lbl.replace("Mr.","").replace("Ms.","").replace("Dr.","").strip().split()
        labels_sg[n] = p[-1][:10] if p else lbl[:10]
    elif ntype == "course":
        labels_sg[n] = " ".join(lbl.split()[:2])
    elif ntype == "section":
        labels_sg[n] = lbl.replace("BTech CSE","CSE").replace("BCA","BCA").replace("Sem","S")
    elif ntype == "timeslot":
        labels_sg[n] = lbl.replace(" Slot ", "S")
    else:
        labels_sg[n] = lbl[:8]
nx.draw_networkx_labels(SG, pos, labels=labels_sg,
                        font_size=5.5, font_color="white", ax=ax_sg)

edge_patches = [mpatches.Patch(color=c, label=r.replace("_"," ").title())
                for r, c in EDGE_COLORS.items()
                if any(d.get("relation") == r for _, _, d in SG.edges(data=True))]
node_patches = [mpatches.Patch(color=c, label=t.capitalize())
                for t, c in TYPE_COLORS.items()
                if any(G.nodes[n].get("node_type") == t for n in SG.nodes())]
ax_sg.legend(handles=edge_patches + node_patches,
             facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
             fontsize=6, loc="lower left",
             title="Edge / Node types", title_fontsize=6.5)
ax_sg.axis("off")

# ── Panel 1-B: Node type distribution (bar chart) ────────────────────────────
ax_nt = fig1.add_subplot(gs[0, 1])
style_ax(ax_nt, "Node Type Distribution", "Count", "Node type")

node_type_counts = defaultdict(int)
for n, d in G.nodes(data=True):
    node_type_counts[d.get("node_type", "unknown")] += 1

types_sorted  = sorted(node_type_counts, key=lambda x: -node_type_counts[x])
counts_sorted = [node_type_counts[t] for t in types_sorted]
colors_sorted = [TYPE_COLORS.get(t, "#888") for t in types_sorted]

bars = ax_nt.barh(types_sorted, counts_sorted, color=colors_sorted,
                  alpha=0.85, edgecolor=BG, linewidth=0.5)
for bar, cnt in zip(bars, counts_sorted):
    ax_nt.text(cnt + 1, bar.get_y() + bar.get_height()/2,
               str(cnt), va="center", color=TEXT, fontsize=9)
ax_nt.set_xlim(0, max(counts_sorted) * 1.15)
ax_nt.tick_params(left=False)
ax_nt.invert_yaxis()

# ── Panel 1-C: Edge type distribution ────────────────────────────────────────
ax_et = fig1.add_subplot(gs[1, 0])
style_ax(ax_et, "Edge Type Distribution", "Count", "Edge type")

edge_type_counts = defaultdict(int)
for u, v, d in G.edges(data=True):
    edge_type_counts[d.get("relation", "unknown")] += 1

etypes  = sorted(edge_type_counts, key=lambda x: -edge_type_counts[x])
ecounts = [edge_type_counts[t] for t in etypes]
ecolors = [EDGE_COLORS.get(t, "#888") for t in etypes]

bars_e = ax_et.barh(etypes, ecounts, color=ecolors, alpha=0.85,
                    edgecolor=BG, linewidth=0.5)
for bar, cnt in zip(bars_e, ecounts):
    ax_et.text(cnt + 2, bar.get_y() + bar.get_height()/2,
               str(cnt), va="center", color=TEXT, fontsize=9)
ax_et.set_xlim(0, max(ecounts) * 1.15)
ax_et.tick_params(left=False)
ax_et.invert_yaxis()

# ── Panel 1-D: Degree distribution (histogram) ────────────────────────────────
ax_deg = fig1.add_subplot(gs[1, 1])
style_ax(ax_deg, "Node Degree Distribution\n(in+out edges per node)",
         "Degree", "Number of nodes")

degrees = [G.degree(n) for n in G.nodes()]
ax_deg.hist(degrees, bins=30, color="#3498DB", alpha=0.8, edgecolor=BG, linewidth=0.4)

# Annotate mean and median
mean_d   = np.mean(degrees)
median_d = np.median(degrees)
ax_deg.axvline(mean_d,   color="#E74C3C", linewidth=1.5, linestyle="--",
               label=f"Mean: {mean_d:.1f}")
ax_deg.axvline(median_d, color="#F39C12", linewidth=1.5, linestyle=":",
               label=f"Median: {median_d:.0f}")
ax_deg.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
ax_deg.text(0.97, 0.95,
            f"Total nodes: {G.number_of_nodes()}\n"
            f"Total edges: {G.number_of_edges()}\n"
            f"Avg degree: {mean_d:.1f}",
            transform=ax_deg.transAxes, ha="right", va="top",
            color=TEXT, fontsize=8,
            bbox=dict(boxstyle="round,pad=0.4", fc=PANEL, ec=GRID))

plt.savefig(OUT_GRAPH, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"  Saved -> {OUT_GRAPH.name}")
plt.close(fig1)


# ========================================================================
# FIGURE 2 — GNN EMBEDDINGS
# 4 panels: t-SNE all | t-SNE faculty | PCA scree | similarity heatmap
# ========================================================================

print("Building Figure 2 — GNN Embeddings...")

fig2 = new_fig(2, 2, "TIMETRIX — GNN Node Embeddings (32-dim)", (22, 14))
gs2  = gridspec.GridSpec(2, 2, figure=fig2, hspace=0.38, wspace=0.32)

# ── Panel 2-A: t-SNE all nodes ────────────────────────────────────────────────
ax_tsne = fig2.add_subplot(gs2[0, 0])
style_ax(ax_tsne, "t-SNE: All Nodes  (colour = node type)",
         "t-SNE dim 1", "t-SNE dim 2")
ax_tsne.grid(False)

perp    = min(30, len(embed_mat) - 1)
coords  = TSNE(n_components=2, perplexity=perp, random_state=42,
               max_iter=1000).fit_transform(embed_mat)

for ntype, color in TYPE_COLORS.items():
    mask = np.array([t == ntype for t in node_types])
    if not mask.any():
        continue
    ax_tsne.scatter(coords[mask, 0], coords[mask, 1],
                    c=color, label=f"{ntype.capitalize()} ({mask.sum()})",
                    alpha=0.82, s=55, edgecolors="none", zorder=3)
    for i in np.where(mask)[0]:
        raw   = G.nodes[all_ids[i]].get("label", "")
        ntype2 = node_types[i]
        if ntype2 == "faculty":
            p   = raw.replace("Mr.","").replace("Ms.","").replace("Dr.","").strip().split()
            lbl = p[-1] if p else raw
        elif ntype2 == "course":
            lbl = " ".join(raw.split()[:2])
        elif ntype2 == "section":
            lbl = raw.replace("BTech CSE","CSE").replace("Sem","S")
        elif ntype2 == "timeslot":
            lbl = raw.replace(" Slot ", "S")
        else:
            lbl = raw
        ax_tsne.annotate(lbl, (coords[i, 0], coords[i, 1]),
                         fontsize=4.5, color=color, alpha=0.7,
                         xytext=(2, 2), textcoords="offset points")

ax_tsne.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT,
               fontsize=8, loc="upper right")

# ── Panel 2-B: t-SNE faculty by department ────────────────────────────────────
ax_fac = fig2.add_subplot(gs2[0, 1])
style_ax(ax_fac, "t-SNE: Faculty Embeddings\n(colour = department)",
         "t-SNE dim 1", "t-SNE dim 2")
ax_fac.grid(False)

fac_mask  = np.array([t == "faculty" for t in node_types])
fac_ids   = [all_ids[i] for i, m in enumerate(fac_mask) if m]
fac_embed = embed_mat[fac_mask]

DEPT_COLORS = {
    "Computer Science" : "#E74C3C", "Humanities"       : "#F39C12",
    "Electronics"      : "#3498DB", "Computer Networks": "#2ECC71",
    "Applied Sciences" : "#9B59B6", "Management"       : "#1ABC9C",
    "Industry"         : "#95A5A6",
}
perp_f    = min(10, max(2, len(fac_embed) - 1))
fac_coords = (TSNE(n_components=2, perplexity=perp_f, random_state=42)
              .fit_transform(fac_embed)
              if len(fac_embed) >= 5
              else PCA(n_components=2).fit_transform(fac_embed))

dept_set = set()
for i, nid in enumerate(fac_ids):
    meta  = node_meta.get(nid, {})
    dept  = meta.get("department", "Computer Science") if meta else "Computer Science"
    color = DEPT_COLORS.get(dept, "#888")
    dept_set.add((dept, color))
    ax_fac.scatter(fac_coords[i, 0], fac_coords[i, 1],
                   c=color, s=75, alpha=0.88, edgecolors="white",
                   linewidths=0.3, zorder=3)
    raw  = G.nodes[nid].get("label", nid)
    p    = raw.replace("Mr.","").replace("Ms.","").replace("Dr.","").strip().split()
    lbl  = p[-1] if p else raw[:12]
    ax_fac.annotate(lbl, (fac_coords[i, 0], fac_coords[i, 1]),
                    fontsize=5.5, color="white", alpha=0.85,
                    xytext=(3, 2), textcoords="offset points")

dept_patches = [mpatches.Patch(color=c, label=d) for d, c in sorted(dept_set)]
ax_fac.legend(handles=dept_patches, facecolor=PANEL, edgecolor=GRID,
              labelcolor=TEXT, fontsize=7, loc="upper right")

# ── Panel 2-C: PCA scree plot (explained variance) ────────────────────────────
ax_pca = fig2.add_subplot(gs2[1, 0])
style_ax(ax_pca, "PCA Scree Plot\n(how much info each principal component holds)",
         "Principal Component", "Explained Variance (%)")

pca_full = PCA(n_components=min(32, len(embed_mat))).fit(embed_mat)
exp_var  = pca_full.explained_variance_ratio_ * 100
cum_var  = np.cumsum(exp_var)
x_idx    = np.arange(1, len(exp_var) + 1)

ax_pca.bar(x_idx, exp_var, color="#3498DB", alpha=0.75,
           label="Individual", edgecolor=BG, linewidth=0.3)
ax2_pca = ax_pca.twinx()
ax2_pca.plot(x_idx, cum_var, color="#E74C3C", linewidth=2,
             marker="o", markersize=3, label="Cumulative")
ax2_pca.tick_params(colors=SUBTLE, labelsize=8)
ax2_pca.set_ylabel("Cumulative Variance (%)", color=SUBTLE, fontsize=8)
ax2_pca.yaxis.label.set_color(SUBTLE)
ax2_pca.set_ylim(0, 105)
for s in ax2_pca.spines.values():
    s.set_edgecolor(GRID)

# Mark 80% and 95% thresholds
for thresh, col in [(80, "#F39C12"), (95, "#2ECC71")]:
    idx_thresh = np.searchsorted(cum_var, thresh)
    if idx_thresh < len(cum_var):
        ax2_pca.axhline(thresh, color=col, linewidth=1, linestyle="--", alpha=0.7)
        ax2_pca.text(len(exp_var) * 0.98, thresh + 1, f"{thresh}%",
                     color=col, fontsize=7, ha="right")

lines1, labels1 = ax_pca.get_legend_handles_labels()
lines2, labels2 = ax2_pca.get_legend_handles_labels()
ax_pca.legend(lines1 + lines2, labels1 + labels2,
              facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

# ── Panel 2-D: Cosine similarity heatmap between node-type centroids ──────────
ax_sim = fig2.add_subplot(gs2[1, 1])
style_ax(ax_sim, "Cosine Similarity Between Node Types\n(centroid of each type's embeddings)")
ax_sim.grid(False)

type_order = ["faculty", "course", "section", "room", "timeslot"]
centroids  = {}
for t in type_order:
    mask = np.array([nt == t for nt in node_types])
    if mask.any():
        vec = embed_mat[mask].mean(axis=0)
        centroids[t] = vec / (np.linalg.norm(vec) + 1e-8)

n_types = len(centroids)
sim_matrix = np.zeros((n_types, n_types))
keys = list(centroids.keys())
for i, ki in enumerate(keys):
    for j, kj in enumerate(keys):
        sim_matrix[i, j] = float(np.dot(centroids[ki], centroids[kj]))

# Custom diverging colormap  (blue=low/dissimilar -> red=high/similar)
cmap = LinearSegmentedColormap.from_list(
    "timetrix", ["#2C3E50", "#2980B9", "#ECF0F1", "#E74C3C", "#922B21"])
im = ax_sim.imshow(sim_matrix, cmap=cmap, vmin=-1, vmax=1, aspect="auto")

ax_sim.set_xticks(range(n_types))
ax_sim.set_yticks(range(n_types))
ax_sim.set_xticklabels([k.capitalize() for k in keys],
                        rotation=35, ha="right", color=TEXT, fontsize=8)
ax_sim.set_yticklabels([k.capitalize() for k in keys],
                        color=TEXT, fontsize=8)

for i in range(n_types):
    for j in range(n_types):
        ax_sim.text(j, i, f"{sim_matrix[i,j]:.2f}",
                    ha="center", va="center", fontsize=8,
                    color="white" if abs(sim_matrix[i,j]) > 0.4 else TEXT)

plt.colorbar(im, ax=ax_sim, fraction=0.046, pad=0.04).ax.tick_params(
    colors=SUBTLE, labelsize=7)

plt.savefig(OUT_GNN, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"  Saved -> {OUT_GNN.name}")
plt.close(fig2)


# ========================================================================
# FIGURE 3 — RANDOM FOREST ENSEMBLE
# 4 panels: feature importances | score distribution |
#           Precision-Recall curve | Calibration diagram
# ========================================================================

print("Building Figure 3 — Random Forest Ensemble...")

# ── Load RF artifacts ─────────────────────────────────────────────────────────
with open(RF_MODEL_PATH, "rb") as f:  rf_model = pickle.load(f)
with open(RF_META_PATH,  "rb") as f:  rf_meta  = pickle.load(f)

scaler     = rf_meta["scaler"]
feat_names = rf_meta["feature_names"]
stats      = rf_meta["stats"]
max_hrs    = rf_meta["max_hours_map"]
threshold  = rf_meta.get("optimal_threshold", 0.5)
embed_dim  = rf_meta.get("embed_dim", 32)

# Load training report
with open(RF_REPORT) as fh:
    report = json.load(fh)

# ── Reconstruct feature vectors from training CSVs for visualization ──────────
# We need actual predictions to draw the score distribution, PR curve, and
# calibration diagram. We rebuild the same feature vectors used in training.

ZERO = np.zeros(embed_dim, dtype=np.float32)

def fac_id(n):     return f"FAC::{n.strip()}"
def ts_id(d, s):   return f"TSL::{d[:3].upper()}_S{s}"
def rm_id(r):      return f"RRM::{str(r).strip()}"

def build_feat(faculty, room, day, slot, is_lab, consec,
               contact_hours, semester_int, course_name,
               fac_weekly_load, fac_today_load=0, max_daily=4):
    fe = embeddings.get(fac_id(faculty), ZERO) if faculty != "TBD" else ZERO
    te = embeddings.get(ts_id(day, slot), ZERO)
    re = embeddings.get(rm_id(room), ZERO)

    max_h    = max_hrs.get(faculty, 18)
    cur_load = fac_weekly_load.get(faculty, 0)
    load_rem = max(0.0, (max_h - cur_load) / max(float(max_h), 1.0))

    actual_slots = stats.get("fac_actual_slots", {}).get(faculty, set())
    is_known     = 1.0 if (day, slot) in actual_slots else 0.0

    freq    = stats.get("fac_course_freq", {}).get((faculty, course_name), 0)
    max_fq  = max((v for (f, _), v in stats.get("fac_course_freq", {}).items()
                   if f == faculty), default=1)
    affinity = freq / max(max_fq, 1)

    slot_pop = stats.get("slot_popularity", {}).get(slot, 0.5)
    day_pop  = stats.get("day_popularity",  {}).get(day, 0.5)

    breadth  = sum(1 for (f, _) in stats.get("fac_course_freq", {}) if f == faculty)
    breadth_n = min(breadth / 10.0, 1.0)

    is_morning    = 1.0 if slot <= 3 else 0.0
    is_post_lunch = 1.0 if slot >= 5 else 0.0
    sem_n         = float(semester_int) / 8.0
    contact_n     = float(contact_hours) / 8.0

    today_ratio  = float(fac_today_load) / max(float(max_daily), 1.0)
    adj_l = stats.get("slot_popularity", {}).get(slot - 1, 0.5)
    adj_r = stats.get("slot_popularity", {}).get(slot + 1, 0.5)
    adj_density = (adj_l + adj_r) / 2.0
    near_cap     = 1.0 if cur_load >= max_h * 0.85 else 0.0

    manual = np.array([
        load_rem, is_known, affinity, slot_pop, day_pop,
        float(is_lab), float(consec),
        is_morning, is_post_lunch, sem_n, contact_n, breadth_n,
        today_ratio, adj_density, near_cap,
    ], dtype=np.float32)
    return np.concatenate([fe, te, re, manual])

# Build positive features from CSV
df  = pd.read_csv(SESSION_CSV)
df.columns = df.columns.str.strip()
df["course_code"] = df["course_code"].fillna("")

named_rows = df[(df["faculty"] != "TBD") & (df["day"] != "Saturday")]
fac_load   = defaultdict(int)
fac_day_load = defaultdict(lambda: defaultdict(int))

X_pos, X_neg = [], []
skipped = 0
for _, row in named_rows.iterrows():
    fac  = str(row["faculty"]).strip()
    day  = str(row["day"]).strip()
    slot = int(row["slot_index"])
    try:
        feat = build_feat(
            faculty=fac, room=str(row["room"]).strip(),
            day=day, slot=slot,
            is_lab=int(row["is_lab"]), consec=int(row["is_consecutive_lab"]),
            contact_hours=int(row["contact_hours_weekly"]),
            semester_int=int(row["semester_int"]),
            course_name=str(row["course_name"]).strip(),
            fac_weekly_load=fac_load,
            fac_today_load=fac_day_load[fac][day],
            max_daily=4,
        )
        if np.any(np.isnan(feat)) or np.any(np.isinf(feat)):
            skipped += 1
            continue
        X_pos.append(feat)
        fac_load[fac] += 1
        fac_day_load[fac][day] += 1
    except Exception:
        skipped += 1

# Build a balanced set of negatives from shuffled faculty/day/slot combinations
rooms_df = pd.read_csv(ROOMS_CSV)
rooms_df.columns = rooms_df.columns.str.strip()
th_rooms = rooms_df[rooms_df["is_lab"] == 0]["room_id"].astype(str).tolist()
rng      = np.random.default_rng(42)
rows_list = named_rows.to_dict("records")
real_triples = {(r["faculty"], r["day"], r["slot_index"]) for r in rows_list}
all_days  = ["Monday","Tuesday","Wednesday","Thursday","Friday"]
all_slots = [1, 2, 3, 4, 5, 6]

n_neg_target = len(X_pos)
attempts     = 0
while len(X_neg) < n_neg_target and attempts < n_neg_target * 10:
    attempts += 1
    row  = rows_list[rng.integers(len(rows_list))]
    fac  = row["faculty"]
    day  = all_days[rng.integers(5)]
    slot = int(all_slots[rng.integers(6)])
    if (fac, day, slot) in real_triples:
        continue
    room = th_rooms[rng.integers(len(th_rooms))] if th_rooms else row["room"]
    try:
        feat = build_feat(
            faculty=fac, room=room, day=day, slot=slot,
            is_lab=0, consec=0,
            contact_hours=int(row["contact_hours_weekly"]),
            semester_int=int(row["semester_int"]),
            course_name=str(row["course_name"]).strip(),
            fac_weekly_load={},
            fac_today_load=0, max_daily=4,
        )
        if not (np.any(np.isnan(feat)) or np.any(np.isinf(feat))):
            X_neg.append(feat)
    except Exception:
        pass

X_vis  = np.vstack(X_pos + X_neg).astype(np.float32)
y_vis  = np.array([1]*len(X_pos) + [0]*len(X_neg), dtype=int)

# Scale and predict
n_feats = getattr(rf_model, "n_features_in_", len(X_vis[0]))
if X_vis.shape[1] == n_feats:
    X_sc  = scaler.transform(X_vis)
    y_scores = rf_model.predict_proba(X_sc)[:, 1]
    print(f"  Scored {len(y_scores)} samples for RF visualization")
else:
    # Fallback: zero-pad / truncate to match
    pad = np.zeros((X_vis.shape[0], n_feats), dtype=np.float32)
    pad[:, :min(X_vis.shape[1], n_feats)] = X_vis[:, :min(X_vis.shape[1], n_feats)]
    X_sc     = scaler.transform(pad)
    y_scores = rf_model.predict_proba(X_sc)[:, 1]
    print(f"  Scored {len(y_scores)} samples (padded to {n_feats})")

# ── Extract feature importances from RF inside the VotingClassifier ───────────
try:
    rf_inner = rf_model.estimators_[0]                             # CalibratedClassifierCV
    inner_rf = rf_inner.calibrated_classifiers_[0].estimator      # RandomForestClassifier
    importances = inner_rf.feature_importances_
except Exception:
    importances = np.zeros(len(feat_names))

top_n  = 20
top_idx = np.argsort(importances)[::-1][:top_n]
top_imp = importances[top_idx]
top_nam = [feat_names[i] if i < len(feat_names) else f"feat_{i}"
           for i in top_idx]

# ─────────────────────────────────────────────────────────────────────────────
fig3 = new_fig(2, 2, "TIMETRIX — Random Forest Ensemble Analysis", (22, 14))
gs3  = gridspec.GridSpec(2, 2, figure=fig3, hspace=0.40, wspace=0.35)

# ── Panel 3-A: Feature importances (top 20, horizontal bar) ──────────────────
ax_fi = fig3.add_subplot(gs3[0, 0])
style_ax(ax_fi, f"Top {top_n} Feature Importances\n(from RF inside VotingClassifier)",
         "Importance score", "Feature")

# Colour bars: embedding dims one colour, manual features another
bar_colors = []
for name in top_nam:
    if name.startswith("fac_emb"):
        bar_colors.append("#E74C3C")
    elif name.startswith("ts_emb"):
        bar_colors.append("#9B59B6")
    elif name.startswith("rm_emb"):
        bar_colors.append("#F39C12")
    else:
        bar_colors.append("#2ECC71")   # manual features

y_pos = np.arange(len(top_nam))
bars_fi = ax_fi.barh(y_pos, top_imp, color=bar_colors, alpha=0.85,
                      edgecolor=BG, linewidth=0.4)
ax_fi.set_yticks(y_pos)
ax_fi.set_yticklabels(top_nam, fontsize=7.5, color=TEXT)
ax_fi.invert_yaxis()
ax_fi.set_xlim(0, top_imp.max() * 1.18)
for bar, imp in zip(bars_fi, top_imp):
    ax_fi.text(imp + 0.001, bar.get_y() + bar.get_height()/2,
               f"{imp:.4f}", va="center", color=TEXT, fontsize=7)

legend_fi = [
    mpatches.Patch(color="#E74C3C", label="Faculty embedding"),
    mpatches.Patch(color="#9B59B6", label="Timeslot embedding"),
    mpatches.Patch(color="#F39C12", label="Room embedding"),
    mpatches.Patch(color="#2ECC71", label="Manual / new features"),
]
ax_fi.legend(handles=legend_fi, facecolor=PANEL, edgecolor=GRID,
             labelcolor=TEXT, fontsize=7.5, loc="lower right")

# ── Panel 3-B: Score distribution (positive vs negative classes) ─────────────
ax_dist = fig3.add_subplot(gs3[0, 1])
style_ax(ax_dist, "Predicted Score Distribution\n(positive = real schedules, negative = bad assignments)",
         "Predicted probability (score)", "Density")

pos_scores = y_scores[y_vis == 1]
neg_scores = y_scores[y_vis == 0]
bins = np.linspace(0, 1, 40)

ax_dist.hist(neg_scores, bins=bins, density=True, alpha=0.65,
             color="#E74C3C", label=f"Negative (bad)  n={len(neg_scores)}")
ax_dist.hist(pos_scores, bins=bins, density=True, alpha=0.65,
             color="#2ECC71", label=f"Positive (real) n={len(pos_scores)}")

ax_dist.axvline(threshold, color="#F39C12", linewidth=2, linestyle="--",
                label=f"Optimal threshold = {threshold:.3f}")

ax_dist.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)
ax_dist.text(0.98, 0.95,
             f"Overlap area shows model uncertainty.\n"
             f"Well-separated = strong model.",
             transform=ax_dist.transAxes, ha="right", va="top",
             color=SUBTLE, fontsize=7.5,
             bbox=dict(boxstyle="round,pad=0.4", fc=PANEL, ec=GRID, alpha=0.8))

# ── Panel 3-C: Precision-Recall curve ────────────────────────────────────────
ax_pr = fig3.add_subplot(gs3[1, 0])
style_ax(ax_pr, "Precision-Recall Curve\n(ideal = top-right corner)",
         "Recall", "Precision")
ax_pr.grid(False)
ax_pr.set_facecolor(PANEL)

precision, recall, pr_thresholds = precision_recall_curve(y_vis, y_scores)
pr_auc = auc(recall, precision)

# Shade the area under the curve
ax_pr.fill_between(recall, precision, alpha=0.15, color="#3498DB")
ax_pr.plot(recall, precision, color="#3498DB", linewidth=2,
           label=f"PR AUC = {pr_auc:.4f}")

# Mark the optimal threshold point
denom = precision[:-1] + recall[:-1]
denom = np.where(denom > 0, denom, 1.0)
f1    = 2 * precision[:-1] * recall[:-1] / denom
best  = int(np.argmax(f1))
ax_pr.scatter(recall[best], precision[best], s=120, color="#E74C3C",
              zorder=5, label=f"Optimal (F1={f1[best]:.3f})\n"
                              f"threshold={pr_thresholds[best]:.3f}")

# Also show baseline (random classifier)
baseline = y_vis.mean()
ax_pr.axhline(baseline, color=SUBTLE, linewidth=1, linestyle=":",
              label=f"Random baseline = {baseline:.2f}")

ax_pr.set_xlim(0, 1.02)
ax_pr.set_ylim(0, 1.05)
ax_pr.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=8)

# CV metrics from training report
ax_pr.text(0.02, 0.08,
           f"CV ROC-AUC : {report.get('cv_roc_auc','?')}\n"
           f"CV F1       : {report.get('cv_f1','?')}\n"
           f"CV Accuracy : {report.get('cv_accuracy','?')}\n"
           f"OOB score   : {report.get('oob_score','?')}",
           transform=ax_pr.transAxes, va="bottom", color=TEXT, fontsize=8,
           bbox=dict(boxstyle="round,pad=0.45", fc=PANEL, ec=GRID))

# ── Panel 3-D: Calibration (reliability) diagram ─────────────────────────────
ax_cal = fig3.add_subplot(gs3[1, 1])
style_ax(ax_cal, "Calibration Diagram (Reliability Curve)\n"
                 "Points on diagonal = perfectly calibrated",
         "Mean predicted probability", "Fraction of positives")
ax_cal.grid(False)
ax_cal.set_facecolor(PANEL)

# Perfect calibration reference line
ax_cal.plot([0, 1], [0, 1], linestyle="--", color=SUBTLE,
            linewidth=1.5, label="Perfect calibration")

# Calibration curve from our model
try:
    frac_pos, mean_pred = calibration_curve(y_vis, y_scores, n_bins=10,
                                             strategy="uniform")
    ax_cal.plot(mean_pred, frac_pos, color="#3498DB", linewidth=2,
                marker="o", markersize=6, label="Ensemble model")
    ax_cal.fill_between(mean_pred, frac_pos, mean_pred, alpha=0.12,
                        color="#3498DB")

    # Annotate deviation from perfect calibration
    max_dev = np.max(np.abs(frac_pos - mean_pred))
    ax_cal.text(0.98, 0.08,
                f"Max calibration error: {max_dev:.3f}\n"
                f"(0 = perfect, <0.05 = very good)",
                transform=ax_cal.transAxes, ha="right", va="bottom",
                color=TEXT, fontsize=8,
                bbox=dict(boxstyle="round,pad=0.4", fc=PANEL, ec=GRID))
except Exception as e:
    ax_cal.text(0.5, 0.5, f"Calibration data\nnot available\n({e})",
                transform=ax_cal.transAxes, ha="center", va="center",
                color=SUBTLE, fontsize=9)

ax_cal.set_xlim(0, 1)
ax_cal.set_ylim(0, 1.05)
ax_cal.legend(facecolor=PANEL, edgecolor=GRID, labelcolor=TEXT, fontsize=9)

# Histogram of predicted probabilities (inset)
ax_inset = ax_cal.inset_axes([0.55, 0.10, 0.40, 0.30])
ax_inset.set_facecolor(BG)
ax_inset.hist(y_scores[y_vis == 0], bins=20, density=True,
              alpha=0.6, color="#E74C3C", label="Neg")
ax_inset.hist(y_scores[y_vis == 1], bins=20, density=True,
              alpha=0.6, color="#2ECC71", label="Pos")
ax_inset.set_title("Score hist", color=TEXT, fontsize=6)
ax_inset.tick_params(colors=SUBTLE, labelsize=5)
for sp in ax_inset.spines.values():
    sp.set_edgecolor(GRID)

plt.savefig(OUT_RF, dpi=150, bbox_inches="tight", facecolor=BG)
print(f"  Saved -> {OUT_RF.name}")
plt.close(fig3)

print("\nAll three visualizations saved:")
print(f"  {OUT_GRAPH}")
print(f"  {OUT_GNN}")
print(f"  {OUT_RF}")
