"""
TIMETRIX — GNN Embedding Visualization v2
Shows clusters, labels, and a subgraph side by side.
Run from inside ml_pipeline/:  py visualize_embeddings.py
"""
import pickle
import numpy as np
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from sklearn.manifold import TSNE
from sklearn.decomposition import PCA
import networkx as nx

BASE = "trained"

with open(f"{BASE}/timetrix_graph.gpickle", "rb") as f:
    G = pickle.load(f)
with open(f"{BASE}/node_embeddings.pkl", "rb") as f:
    embeddings = pickle.load(f)

all_ids    = [n for n in G.nodes() if n in embeddings]
node_types = [G.nodes[n].get("node_type", "?") for n in all_ids]
embed_mat  = np.array([embeddings[n] for n in all_ids])

TYPE_COLORS = {
    "faculty"  : "#E74C3C",
    "course"   : "#3498DB",
    "section"  : "#2ECC71",
    "room"     : "#F39C12",
    "timeslot" : "#9B59B6",
}

fig = plt.figure(figsize=(24, 14))
fig.patch.set_facecolor("#0F1117")

# ── Chart 1: t-SNE — ALL nodes, color by type, labeled ───────────────────────
ax1 = fig.add_subplot(1, 3, 1)
ax1.set_facecolor("#1A1D27")
ax1.set_title("t-SNE: All 344 Nodes\n(color = node type)", color="white", fontsize=11)

coords = TSNE(n_components=2, perplexity=20, random_state=42,
              ).fit_transform(embed_mat)

for ntype, color in TYPE_COLORS.items():
    mask = np.array([t == ntype for t in node_types])
    if mask.sum() == 0:
        continue
    ax1.scatter(coords[mask, 0], coords[mask, 1],
                c=color, label=f"{ntype.capitalize()} ({mask.sum()})",
                alpha=0.85, s=55, edgecolors="none", zorder=3)

    # Label every node with a short name
    idxs = np.where(mask)[0]
    for i in idxs:
        raw = G.nodes[all_ids[i]].get("label", "")
        # Shorten labels
        if ntype == "faculty":
            # Last name only
            parts = raw.replace("Mr.","").replace("Ms.","").replace("Dr.","").strip().split()
            lbl = parts[-1] if parts else raw
        elif ntype == "course":
            words = raw.split()
            lbl = " ".join(words[:2]) if len(words) >= 2 else raw
        elif ntype == "section":
            lbl = raw.replace("BTech CSE","CSE").replace("Sem","S")
        elif ntype == "room":
            lbl = raw
        else:
            lbl = raw.replace(" Slot ", "S")

        ax1.annotate(lbl, (coords[i, 0], coords[i, 1]),
                     fontsize=5, color=color, alpha=0.75,
                     xytext=(2, 2), textcoords="offset points")

ax1.legend(facecolor="#1A1D27", edgecolor="#555", labelcolor="white",
           fontsize=8, loc="upper right")
ax1.set_xlabel("t-SNE dim 1", color="#888", fontsize=8)
ax1.set_ylabel("t-SNE dim 2", color="#888", fontsize=8)
ax1.tick_params(colors="#555")
for s in ax1.spines.values():
    s.set_edgecolor("#333")


# ── Chart 2: t-SNE — Faculty only, labeled with names ─────────────────────────
ax2 = fig.add_subplot(1, 3, 2)
ax2.set_facecolor("#1A1D27")
ax2.set_title("t-SNE: Faculty Embeddings\n(similar teachers = closer together)",
              color="white", fontsize=11)

fac_mask  = np.array([t == "faculty" for t in node_types])
fac_ids   = [all_ids[i] for i, m in enumerate(fac_mask) if m]
fac_embed = embed_mat[fac_mask]
fac_types = [G.nodes[n].get("node_type","?") for n in fac_ids]

if len(fac_embed) >= 5:
    fac_coords = TSNE(n_components=2, perplexity=min(10, len(fac_embed)-1),
                      random_state=42, ).fit_transform(fac_embed)
else:
    fac_coords = PCA(n_components=2).fit_transform(fac_embed)

# Color faculty by department
from collections import defaultdict
dept_colors = {
    "Computer Science" : "#E74C3C",
    "Humanities"       : "#F39C12",
    "Electronics"      : "#3498DB",
    "Computer Networks": "#2ECC71",
    "Applied Sciences" : "#9B59B6",
    "Management"       : "#1ABC9C",
    "Industry"         : "#95A5A6",
}

# Load node metadata for department info
try:
    with open(f"{BASE}/node_metadata.pkl", "rb") as f:
        node_meta = pickle.load(f)
except:
    node_meta = {}

dept_set = set()
for i, nid in enumerate(fac_ids):
    meta = node_meta.get(nid, {})
    dept = meta.get("department", "Computer Science") if meta else "Computer Science"
    color = dept_colors.get(dept, "#888888")
    dept_set.add((dept, color))
    ax2.scatter(fac_coords[i, 0], fac_coords[i, 1],
                c=color, s=80, alpha=0.9, edgecolors="white",
                linewidths=0.3, zorder=3)
    # Full last name label
    raw = G.nodes[nid].get("label", nid)
    parts = raw.replace("Mr.","").replace("Ms.","").replace("Dr.","").strip().split()
    lbl = parts[-1] if parts else raw[:12]
    ax2.annotate(lbl, (fac_coords[i, 0], fac_coords[i, 1]),
                 fontsize=6, color="white", alpha=0.85,
                 xytext=(3, 2), textcoords="offset points")

dept_patches = [mpatches.Patch(color=c, label=d)
                for d, c in sorted(dept_set)]
ax2.legend(handles=dept_patches, facecolor="#1A1D27", edgecolor="#555",
           labelcolor="white", fontsize=7, loc="upper right")
ax2.set_xlabel("t-SNE dim 1", color="#888", fontsize=8)
ax2.set_ylabel("t-SNE dim 2", color="#888", fontsize=8)
ax2.tick_params(colors="#555")
for s in ax2.spines.values():
    s.set_edgecolor("#333")


# ── Chart 3: Schedule subgraph with edges drawn ───────────────────────────────
ax3 = fig.add_subplot(1, 3, 3)
ax3.set_facecolor("#1A1D27")
ax3.set_title("Actual Schedule Graph\nBTech CSE Sem4 — selected sections",
              color="white", fontsize=11)

# Pick 2-3 sections + their direct neighbors only (keep readable)
target_sections = []
for n, d in G.nodes(data=True):
    if d.get("node_type") == "section":
        lbl = d.get("label","")
        if "4" in lbl and ("Sem4 A" in lbl or "Sem4 B" in lbl or "Sem4 C" in lbl):
            target_sections.append(n)
            if len(target_sections) == 3:
                break

if not target_sections:
    target_sections = [n for n, d in G.nodes(data=True)
                       if d.get("node_type") == "section"][:3]

# 1-hop subgraph only
subgraph_nodes = set(target_sections)
for s in target_sections:
    # Get top-N neighbors by edge weight
    out_edges = sorted(G.out_edges(s, data=True),
                       key=lambda e: e[2].get("weight", 1), reverse=True)[:8]
    in_edges  = sorted(G.in_edges(s, data=True),
                       key=lambda e: e[2].get("weight", 1), reverse=True)[:4]
    subgraph_nodes.update([v for _, v, _ in out_edges])
    subgraph_nodes.update([u for u, _, _ in in_edges])

SG    = G.subgraph(subgraph_nodes).copy()
pos   = nx.spring_layout(SG, seed=7, k=3.0, iterations=80)

EDGE_REL_COLORS = {
    "teaches"     : "#E74C3C",
    "scheduled_at": "#9B59B6",
    "uses"        : "#F39C12",
    "belongs_to"  : "#3498DB",
    "occupied_at" : "#2ECC71",
    "used_at"     : "#888888",
    "teaches_in"  : "#E67E22",
}

# Draw edges colored by relation type
for rel, ecol in EDGE_REL_COLORS.items():
    rel_edges = [(u, v) for u, v, d in SG.edges(data=True)
                 if d.get("relation") == rel]
    if not rel_edges:
        continue
    nx.draw_networkx_edges(
        SG, pos, edgelist=rel_edges,
        edge_color=ecol, alpha=0.6, width=1.2,
        arrows=True, arrowsize=10,
        connectionstyle="arc3,rad=0.12",
        ax=ax3
    )

# Draw nodes
for ntype, color in TYPE_COLORS.items():
    ns = [n for n in SG.nodes() if G.nodes[n].get("node_type") == ntype]
    if not ns:
        continue
    sizes = [500 if n in target_sections else 180 for n in ns]
    nx.draw_networkx_nodes(SG, pos, nodelist=ns, node_color=color,
                           node_size=sizes, alpha=0.95, ax=ax3)

# Labels — short
labels = {}
for n in SG.nodes():
    lbl  = G.nodes[n].get("label", "")
    ntype = G.nodes[n].get("node_type","")
    if ntype == "faculty":
        parts = lbl.replace("Mr.","").replace("Ms.","").replace("Dr.","").strip().split()
        labels[n] = parts[-1][:10] if parts else lbl[:10]
    elif ntype == "course":
        labels[n] = " ".join(lbl.split()[:2])
    elif ntype == "section":
        labels[n] = lbl.replace("BTech CSE","CSE").replace("Sem","S")
    elif ntype == "timeslot":
        labels[n] = lbl.replace(" Slot ","S")
    else:
        labels[n] = lbl[:8]

nx.draw_networkx_labels(SG, pos, labels=labels,
                        font_size=6, font_color="white", ax=ax3)

# Legend — edge types
edge_patches = [mpatches.Patch(color=c, label=r.replace("_"," ").title())
                for r, c in EDGE_REL_COLORS.items()
                if any(d.get("relation")==r for _,_,d in SG.edges(data=True))]
node_patches = [mpatches.Patch(color=c, label=t.capitalize())
                for t, c in TYPE_COLORS.items()
                if any(G.nodes[n].get("node_type")==t for n in SG.nodes())]

ax3.legend(handles=edge_patches + node_patches,
           facecolor="#1A1D27", edgecolor="#555", labelcolor="white",
           fontsize=6.5, loc="lower left",
           title="Edge types / Node types",
           title_fontsize=7)
ax3.axis("off")

fig.suptitle("TIMETRIX GNN — Embeddings & Graph Structure",
             color="white", fontsize=15, fontweight="bold", y=1.01)

plt.tight_layout()
out = "trained/embeddings_tsne.png"
plt.savefig(out, dpi=150, bbox_inches="tight", facecolor="#0F1117")
print(f"Saved → {out}")