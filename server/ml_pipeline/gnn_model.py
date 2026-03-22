"""
TIMETRIX — GNN Model (GraphSAGE)
==================================
Trains a 2-layer GraphSAGE on the timetable graph using link prediction
as the self-supervised task.

After training, extracts 32-dim embeddings for every node.
These embeddings are the input feature vectors for the Random Forest.

Architecture:
    Input node features (5-8 dim, per node type)
        → Linear projection to 64-dim (one per node type)
        → GraphSAGE Layer 1  (64 → 64)
        → ReLU + Dropout(0.3)
        → GraphSAGE Layer 2  (64 → 32)
        → 32-dim node embedding

Training task: Link Prediction
    Positive pairs : edges that exist in the graph (real assignments)
    Negative pairs : randomly sampled non-edges (synthetic violations)
    Loss           : Binary Cross Entropy on dot-product similarity scores

Run:
    python ml_pipeline/gnn_model.py

Output:
    ml_pipeline/trained/gnn_model.pt          — saved model weights
    ml_pipeline/trained/node_embeddings.pkl   — {node_id: 32-dim vector}
    ml_pipeline/trained/gnn_training_log.json — loss curve + metrics
"""

import os
import json
import pickle
import logging
import random
import numpy as np
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F 
from torch.optim import Adam
from torch.optim.lr_scheduler import ReduceLROnPlateau 

# PyTorch Geometric
from torch_geometric.nn import SAGEConv
from torch_geometric.utils import negative_sampling, dropout_edge
from torch_geometric.data import HeteroData
import torch_geometric.transforms as T

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s"
)
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────────────────────────────────────
# PATHS
# ─────────────────────────────────────────────────────────────────────────────

BASE_DIR   = Path(__file__).resolve().parent.parent
TRAIN_DIR  = BASE_DIR / "ml_pipeline" / "trained"

GRAPH_PATH      = TRAIN_DIR / "timetrix_graph.gpickle"
FEATURES_PATH   = TRAIN_DIR / "node_features.pkl"
META_PATH       = TRAIN_DIR / "node_metadata.pkl"

MODEL_PATH      = TRAIN_DIR / "gnn_model.pt"
EMBED_PATH      = TRAIN_DIR / "node_embeddings.pkl"
LOG_PATH        = TRAIN_DIR / "gnn_training_log.json"

# ─────────────────────────────────────────────────────────────────────────────
# HYPERPARAMETERS
# ─────────────────────────────────────────────────────────────────────────────

HIDDEN_DIM   = 64    # projection layer output
EMBED_DIM    = 32    # final embedding dimension
DROPOUT      = 0.3
LEARNING_RATE = 0.005
WEIGHT_DECAY  = 1e-4
EPOCHS       = 150
PATIENCE     = 20    # early stopping patience
NEG_RATIO    = 2     # negative samples per positive edge
SEED         = 42

# Node type → input feature dimension (must match graph_builder.py exactly)
# timeslot upgraded from 6 → 8 to accommodate sinusoidal cyclic encoding
NODE_FEAT_DIMS = {
    "faculty"  : 8,
    "course"   : 7,
    "section"  : 5,
    "room"     : 6,
    "timeslot" : 8,
}

# Edge types used for link prediction training
# We train on all edge types so the GNN learns all relationship patterns
TRAIN_EDGE_TYPES = [
    "teaches",
    "occupied_at",
    "belongs_to",
    "scheduled_at",
    "uses",
    "used_at",
    "teaches_in",
]


# ─────────────────────────────────────────────────────────────────────────────
# GRAPH → PYTORCH GEOMETRIC CONVERSION
# NetworkX graph → flat node list + edge index tensors
# ─────────────────────────────────────────────────────────────────────────────

def nx_to_pyg(G, node_features):
    """
    Convert NetworkX heterogeneous graph to flat PyG-compatible tensors.

    Returns:
        node_ids      : list of all node IDs (string), index = node integer
        x             : FloatTensor (N, max_feat_dim) — padded feature matrix
        edge_index    : LongTensor (2, E) — all edges combined
        edge_type_ids : LongTensor (E,)   — edge type index per edge
        node_type_ids : LongTensor (N,)   — node type index per node
        type_masks    : dict {type_name: bool tensor} — which rows are this type
    """
    import networkx as nx

    NODE_TYPES = list(NODE_FEAT_DIMS.keys())
    EDGE_TYPES = TRAIN_EDGE_TYPES

    node_type_to_idx = {t: i for i, t in enumerate(NODE_TYPES)}
    edge_type_to_idx = {t: i for i, t in enumerate(EDGE_TYPES)}

    # Build ordered node list
    node_ids = list(G.nodes())
    node_to_int = {nid: i for i, nid in enumerate(node_ids)}
    N = len(node_ids)

    # Max feature dimension for padding
    max_dim = max(NODE_FEAT_DIMS.values())  # 8

    # Feature matrix — pad all vectors to max_dim
    x_list = []
    node_type_ids = []
    for nid in node_ids:
        feat     = node_features.get(nid, np.zeros(4, dtype=np.float32))
        ntype    = G.nodes[nid].get("node_type", "course")
        type_idx = node_type_to_idx.get(ntype, 0)
        node_type_ids.append(type_idx)
        # Pad to max_dim
        padded = np.zeros(max_dim, dtype=np.float32)
        padded[:len(feat)] = feat
        x_list.append(padded)

    x             = torch.tensor(np.array(x_list), dtype=torch.float)
    node_type_ids = torch.tensor(node_type_ids,     dtype=torch.long)

    # Edge tensors
    src_list       = []
    dst_list       = []
    etype_list     = []

    for u, v, d in G.edges(data=True):
        rel  = d.get("relation", "")
        eidx = edge_type_to_idx.get(rel, -1)
        if eidx < 0:
            continue
        src_list.append(node_to_int[u])
        dst_list.append(node_to_int[v])
        etype_list.append(eidx)

    edge_index    = torch.tensor([src_list, dst_list], dtype=torch.long)
    edge_type_ids = torch.tensor(etype_list,            dtype=torch.long)

    # Type masks for per-type projection
    type_masks = {}
    for tname, tidx in node_type_to_idx.items():
        type_masks[tname] = (node_type_ids == tidx)

    log.info(f"  Nodes: {N}, Edges: {len(src_list)}")
    return node_ids, x, edge_index, edge_type_ids, node_type_ids, type_masks


# ─────────────────────────────────────────────────────────────────────────────
# MODEL DEFINITION
# ─────────────────────────────────────────────────────────────────────────────

class TimetrixGNN(nn.Module):
    """
    2-layer GraphSAGE with per-node-type input projections.

    Why per-type projections:
        Faculty has 8 features, course has 7, section has 5, etc.
        We can't just pad them and feed to the same linear because
        the meaning of position 6 differs by node type.
        Each type gets its own Linear(feat_dim → hidden_dim) that
        maps its specific features into a shared 64-dim space.
        After projection all nodes live in the same space and can
        exchange messages freely through GraphSAGE.
    """

    def __init__(self, hidden_dim=HIDDEN_DIM, embed_dim=EMBED_DIM,
                 dropout=DROPOUT):
        super().__init__()

        # Per-type input projection layers
        self.proj = nn.ModuleDict({
            ntype: nn.Linear(feat_dim, hidden_dim)
            for ntype, feat_dim in NODE_FEAT_DIMS.items()
        })

        # GraphSAGE message passing layers
        # Both layers operate on the projected hidden_dim space
        self.sage1 = SAGEConv(hidden_dim, hidden_dim)
        self.sage2 = SAGEConv(hidden_dim, embed_dim)

        self.dropout = nn.Dropout(dropout)
        self.bn1     = nn.BatchNorm1d(hidden_dim)
        # Second BatchNorm normalises the final 32-dim embeddings so their
        # scale stays consistent regardless of graph size — important for
        # downstream use by the Random Forest scorer.
        self.bn2     = nn.BatchNorm1d(embed_dim)

    def forward(self, x, edge_index, node_type_ids, type_masks):
        """
        x             : (N, max_feat_dim) padded raw features
        edge_index    : (2, E)
        node_type_ids : (N,)
        type_masks    : dict {type_name: bool tensor}
        """
        N = x.size(0)
        h = torch.zeros(N, HIDDEN_DIM, device=x.device)

        # Apply per-type projection — each type uses its own Linear
        for tname, mask in type_masks.items():
            if mask.sum() == 0:
                continue
            feat_dim = NODE_FEAT_DIMS[tname]
            # Extract the relevant features (first feat_dim columns)
            x_type   = x[mask, :feat_dim]
            h[mask]  = F.relu(self.proj[tname](x_type))

        # Layer 1 — message passing
        h = self.sage1(h, edge_index)
        h = self.bn1(h)
        h = F.relu(h)
        h = self.dropout(h)

        # Layer 2 — message passing → final 32-dim embedding
        h = self.sage2(h, edge_index)
        h = self.bn2(h)   # normalise final embeddings for RF stability

        return h   # (N, embed_dim) — no activation on final layer


# ─────────────────────────────────────────────────────────────────────────────
# LINK PREDICTION TRAINING
# ─────────────────────────────────────────────────────────────────────────────

def compute_link_loss(embeddings, pos_edge_index, neg_edge_index):
    """
    Binary cross-entropy loss for link prediction.

    Positive edges: dot product should be high (close to 1 after sigmoid)
    Negative edges: dot product should be low (close to 0 after sigmoid)
    """
    # Positive pairs
    src_pos = embeddings[pos_edge_index[0]]   # (E_pos, embed_dim)
    dst_pos = embeddings[pos_edge_index[1]]
    pos_score = (src_pos * dst_pos).sum(dim=1)  # dot product per pair

    # Negative pairs
    src_neg = embeddings[neg_edge_index[0]]
    dst_neg = embeddings[neg_edge_index[1]]
    neg_score = (src_neg * dst_neg).sum(dim=1)

    scores = torch.cat([pos_score, neg_score])
    labels = torch.cat([
        torch.ones(pos_score.size(0)),
        torch.zeros(neg_score.size(0))
    ]).to(embeddings.device)

    loss = F.binary_cross_entropy_with_logits(scores, labels)
    return loss


def link_prediction_accuracy(embeddings, pos_edge_index, neg_edge_index):
    """Accuracy of link prediction on current batch."""
    with torch.no_grad():
        src_pos  = embeddings[pos_edge_index[0]]
        dst_pos  = embeddings[pos_edge_index[1]]
        pos_score = torch.sigmoid((src_pos * dst_pos).sum(dim=1))

        src_neg  = embeddings[neg_edge_index[0]]
        dst_neg  = embeddings[neg_edge_index[1]]
        neg_score = torch.sigmoid((src_neg * dst_neg).sum(dim=1))

        pos_correct = (pos_score > 0.5).float().mean().item()
        neg_correct = (neg_score < 0.5).float().mean().item()
        return (pos_correct + neg_correct) / 2


def train(model, x, edge_index, node_type_ids, type_masks,
          optimizer, scheduler, num_nodes):
    """One full training run with early stopping."""

    model.train()
    history = []
    best_loss     = float("inf")
    patience_left = PATIENCE
    best_weights  = None

    for epoch in range(1, EPOCHS + 1):
        optimizer.zero_grad()

        # DropEdge regularisation — randomly remove ~10% of edges each epoch.
        # This prevents the GNN from memorising specific edge patterns and
        # forces it to learn robust node representations even when some
        # connections are missing. Only active during training (model.train()).
        edge_index_drop, _ = dropout_edge(
            edge_index, p=0.10, force_undirected=False, training=model.training
        )

        # Forward pass (uses dropped edges for message passing)
        embeddings = model(x, edge_index_drop, node_type_ids, type_masks)

        # Positive edges — use the FULL edge set for the link prediction loss
        # (we want to predict all real edges, even ones that were dropped above)
        pos_edge_index = edge_index

        # Negative edges — randomly sample non-edges
        neg_edge_index = negative_sampling(
            edge_index        = pos_edge_index,
            num_nodes         = num_nodes,
            num_neg_samples   = pos_edge_index.size(1) * NEG_RATIO,
            method            = "sparse",
        )

        loss = compute_link_loss(embeddings, pos_edge_index, neg_edge_index)
        acc  = link_prediction_accuracy(embeddings, pos_edge_index, neg_edge_index)

        loss.backward()
        # Gradient clipping — prevents exploding gradients on small graphs
        torch.nn.utils.clip_grad_norm_(model.parameters(), max_norm=1.0)
        optimizer.step()
        scheduler.step(loss)

        loss_val = loss.item()
        history.append({"epoch": epoch, "loss": loss_val, "acc": acc})

        if epoch % 10 == 0 or epoch == 1:
            log.info(f"  Epoch {epoch:3d}/{EPOCHS} | "
                     f"loss={loss_val:.4f} | acc={acc:.4f}")

        # Early stopping: if loss hasn't improved for PATIENCE epochs, stop.
        # Saves the best model weights so we can restore them after stopping.
        if loss_val < best_loss - 1e-4:
            best_loss     = loss_val
            patience_left = PATIENCE
            best_weights  = {k: v.clone() for k, v in model.state_dict().items()}
        else:
            patience_left -= 1
            if patience_left == 0:
                log.info(f"  Early stopping at epoch {epoch} "
                         f"(best loss: {best_loss:.4f})")
                break

    # Restore best weights
    if best_weights:
        model.load_state_dict(best_weights)

    return history, best_loss


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING EXTRACTION
# ─────────────────────────────────────────────────────────────────────────────

def extract_embeddings(model, x, edge_index, node_type_ids,
                       type_masks, node_ids):
    """
    Run inference to get 32-dim embedding for every node.
    Returns dict: {node_id (string) → np.array shape (32,)}
    """
    model.eval()
    with torch.no_grad():
        embeddings = model(x, edge_index, node_type_ids, type_masks)

    embeddings_np = embeddings.cpu().numpy()   # (N, 32)

    result = {}
    for i, nid in enumerate(node_ids):
        result[nid] = embeddings_np[i]

    return result


# ─────────────────────────────────────────────────────────────────────────────
# EMBEDDING VALIDATION
# ─────────────────────────────────────────────────────────────────────────────

def validate_embeddings(embeddings, node_meta):
    """
    Sanity checks on learned embeddings.

    Key check: faculty who teach the same subject should have
    similar embeddings (close in cosine distance).
    Faculty who teach completely different subjects should be far apart.
    """
    log.info("Validating embeddings...")

    issues = []

    # Check 1 — no NaN/Inf
    bad = sum(
        1 for v in embeddings.values()
        if np.any(np.isnan(v)) or np.any(np.isinf(v))
    )
    if bad > 0:
        issues.append(f"{bad} embeddings contain NaN/Inf")
    else:
        log.info("  [OK] No NaN/Inf in embeddings")

    # Check 2 — embeddings are not all identical (model collapsed)
    fac_embeds = np.array([
        v for k, v in embeddings.items()
        if k.startswith("FAC::")
    ])
    if len(fac_embeds) > 1:
        std = fac_embeds.std(axis=0).mean()
        if std < 0.01:
            issues.append(f"Faculty embeddings have very low variance ({std:.4f}) — model may have collapsed")
        else:
            log.info(f"  [OK] Faculty embedding variance: {std:.4f}")

    # Check 3 — cosine similarity sanity
    # Mukesh Rajput and Pradumb Dhyani both teach web programming labs
    # They should be more similar than Mukesh Rajput and Manvi Chopra (UHV)
    def cosine(a, b):
        return np.dot(a, b) / (np.linalg.norm(a) * np.linalg.norm(b) + 1e-8)

    fac_mr  = embeddings.get("FAC::Mr. Mukesh Rajput")
    fac_mc  = embeddings.get("FAC::Ms. Manvi Chopra")
    fac_pd  = embeddings.get("FAC::Mr. Pradumb Dhyani")

    if fac_mr is not None and fac_mc is not None and fac_pd is not None:
        sim_similar = cosine(fac_mr, fac_pd)   # both web/lab teachers
        sim_differ  = cosine(fac_mr, fac_mc)   # web vs UHV — should be lower
        log.info(f"  Similarity check: Mukesh-Pradumb={sim_similar:.3f}, "
                 f"Mukesh-Manvi={sim_differ:.3f}")
        if sim_similar > sim_differ:
            log.info("  [OK] Similar faculty are closer than dissimilar faculty")
        else:
            log.info("  [INFO] Similarity ordering not as expected "
                     "(acceptable with limited data)")

    # Check 4 — lab rooms should cluster together
    lab_rooms    = [k for k, v in node_meta.items()
                    if k.startswith("RRM::") and v.get("is_lab") == 1]
    theory_rooms = [k for k, v in node_meta.items()
                    if k.startswith("RRM::") and v.get("is_lab") == 0]

    if len(lab_rooms) >= 2 and len(theory_rooms) >= 2:
        lab_vecs    = np.array([embeddings[r] for r in lab_rooms if r in embeddings])
        theory_vecs = np.array([embeddings[r] for r in theory_rooms if r in embeddings])
        if len(lab_vecs) >= 2 and len(theory_vecs) >= 2:
            avg_within_lab = np.mean([
                cosine(lab_vecs[i], lab_vecs[j])
                for i in range(len(lab_vecs))
                for j in range(i+1, len(lab_vecs))
            ])
            avg_cross = np.mean([
                cosine(l, t)
                for l in lab_vecs for t in theory_vecs
            ])
            log.info(f"  Room clustering: within-lab={avg_within_lab:.3f}, "
                     f"lab-vs-theory={avg_cross:.3f}")
            if avg_within_lab > avg_cross:
                log.info("  [OK] Lab rooms cluster together in embedding space")

    return issues


# ─────────────────────────────────────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────────────────────────────────────

def main():
    torch.manual_seed(SEED)
    random.seed(SEED)
    np.random.seed(SEED)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    log.info(f"Device: {device}")

    # ── Load graph artifacts ──────────────────────────────────────────────────
    log.info("Loading graph artifacts...")

    with open(GRAPH_PATH,    "rb") as f: G             = pickle.load(f)
    with open(FEATURES_PATH, "rb") as f: node_features = pickle.load(f)
    with open(META_PATH,     "rb") as f: node_meta     = pickle.load(f)

    log.info(f"  Nodes: {G.number_of_nodes()}, Edges: {G.number_of_edges()}")

    # ── Convert to PyG tensors ────────────────────────────────────────────────
    log.info("Converting to PyG format...")
    node_ids, x, edge_index, edge_type_ids, node_type_ids, type_masks = \
        nx_to_pyg(G, node_features)

    x             = x.to(device)
    edge_index    = edge_index.to(device)
    node_type_ids = node_type_ids.to(device)
    type_masks    = {k: v.to(device) for k, v in type_masks.items()}
    num_nodes     = x.size(0)

    # ── Build model ───────────────────────────────────────────────────────────
    log.info("Building model...")
    model = TimetrixGNN(
        hidden_dim = HIDDEN_DIM,
        embed_dim  = EMBED_DIM,
        dropout    = DROPOUT,
    ).to(device)

    total_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    log.info(f"  Trainable parameters: {total_params:,}")

    optimizer = Adam(
        model.parameters(),
        lr           = LEARNING_RATE,
        weight_decay = WEIGHT_DECAY,
    )
    scheduler = ReduceLROnPlateau(
        optimizer, mode="min", factor=0.5, patience=10
    )

    # ── Train ─────────────────────────────────────────────────────────────────
    log.info(f"Training for up to {EPOCHS} epochs...")
    history, best_loss = train(
        model, x, edge_index, node_type_ids, type_masks, optimizer,
        scheduler, num_nodes
    )

    # ── Extract embeddings ────────────────────────────────────────────────────
    log.info("Extracting node embeddings...")
    embeddings = extract_embeddings(
        model, x, edge_index, node_type_ids, type_masks, node_ids
    )

    # ── Validate embeddings ───────────────────────────────────────────────────
    issues = validate_embeddings(embeddings, node_meta)
    if issues:
        for issue in issues:
            log.warning(f"  {issue}")
    else:
        log.info("  All embedding checks passed")

    # ── Save ──────────────────────────────────────────────────────────────────
    log.info("Saving...")

    # Model weights
    torch.save({
        "model_state_dict" : model.state_dict(),
        "hyperparams"      : {
            "hidden_dim"  : HIDDEN_DIM,
            "embed_dim"   : EMBED_DIM,
            "dropout"     : DROPOUT,
            "epochs_run"  : len(history),
            "best_loss"   : best_loss,
        },
        "node_ids"         : node_ids,
    }, MODEL_PATH)

    # Embeddings
    with open(EMBED_PATH, "wb") as f:
        pickle.dump(embeddings, f, protocol=pickle.HIGHEST_PROTOCOL)

    # Training log
    training_log = {
        "best_loss"   : best_loss,
        "epochs_run"  : len(history),
        "final_acc"   : history[-1]["acc"] if history else 0,
        "history"     : history,
        "embedding_shape": [num_nodes, EMBED_DIM],
        "validation_issues": issues,
    }
    with open(LOG_PATH, "w") as f:
        json.dump(training_log, f, indent=2)

    log.info(f"  Model      → {MODEL_PATH}")
    log.info(f"  Embeddings → {EMBED_PATH}")
    log.info(f"  Log        → {LOG_PATH}")
    log.info(f"Done. Best loss: {best_loss:.4f}, "
             f"Final acc: {training_log['final_acc']:.4f}")

    return model, embeddings


if __name__ == "__main__":
    main()