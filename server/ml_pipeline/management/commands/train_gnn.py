from django.core.management.base import BaseCommand
from ml_pipeline import gnn_model


class Command(BaseCommand):
    help = "Train the GNN (GraphSAGE) model and export 32-dim node embeddings"

    def handle(self, *args, **options):
        self.stdout.write("Training GNN model...")
        result = gnn_model.main()
        n_nodes = len(result) if isinstance(result, dict) else 0
        self.stdout.write(
            self.style.SUCCESS(f"Done. Exported embeddings for {n_nodes} nodes.")
        )
