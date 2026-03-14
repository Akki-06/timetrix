import pickle
import numpy as np
import matplotlib.pyplot as plt
from sklearn.manifold import TSNE

BASE = "ml_pipeline/trained"

with open(f"{BASE}/timetrix_graph.gpickle", "rb") as f:
    G = pickle.load(f)
with open(f"{BASE}/node_embeddings.pkl", "rb") as f:
    embeddings = pickle.load(f)

all_ids    = list(embeddings.keys())
node_types = [G.nodes[n].get("node_type", "?") for n in all_ids]
embed_mat  = np.array([embeddings[n] for n in all_ids])  # (344, 32)

coords = TSNE(n_components=2, perplexity=20, random_state=42).fit_transform(embed_mat)

TYPE_COLORS = {
    "faculty": "#E74C3C", "course": "#3498DB", "section": "#2ECC71",
    "room": "#F39C12",    "timeslot": "#9B59B6"
}

plt.figure(figsize=(12, 8), facecolor="#0F1117")
ax = plt.gca()
ax.set_facecolor("#1A1D27")

for ntype, color in TYPE_COLORS.items():
    mask = np.array([t == ntype for t in node_types])
    if mask.sum() == 0:
        continue
    ax.scatter(coords[mask, 0], coords[mask, 1],
               c=color, label=ntype.capitalize(),
               alpha=0.8, s=60, edgecolors="none")

    # Label a few nodes per type
    indices = np.where(mask)[0][:3]
    for i in indices:
        label = G.nodes[all_ids[i]].get("label", "")[:20]
        ax.annotate(label, (coords[i, 0], coords[i, 1]),
                    fontsize=6, color="white", alpha=0.7)

ax.legend(facecolor="#1A1D27", edgecolor="#444", labelcolor="white")
ax.set_title("GNN Node Embeddings — t-SNE 2D", color="white", fontsize=13)
ax.tick_params(colors="#888")
for spine in ax.spines.values():
    spine.set_edgecolor("#444")

plt.tight_layout()
plt.savefig("ml_pipeline/trained/embeddings_tsne.png", dpi=150, bbox_inches="tight")
plt.show()  # opens interactive window — remove if running headless
print("Saved to ml_pipeline/trained/embeddings_tsne.png")
