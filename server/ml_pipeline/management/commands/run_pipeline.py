from pathlib import Path

from django.core.management.base import BaseCommand
from ml_pipeline import graph_builder, gnn_model, random_forest_model

TRAINED_DIR = Path(__file__).resolve().parent.parent.parent / "trained"


class Command(BaseCommand):
    help = (
        "Run the full ML pipeline: "
        "graph_builder -> GNN training -> RF training"
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--skip-graph",
            action="store_true",
            help="Skip graph building — reuse existing timetrix_graph.gpickle",
        )
        parser.add_argument(
            "--skip-gnn",
            action="store_true",
            help="Skip GNN training — reuse existing node_embeddings.pkl",
        )

    def handle(self, *args, **options):
        # Phase 1: Graph
        if options["skip_graph"]:
            graph_path = TRAINED_DIR / "timetrix_graph.gpickle"
            if not graph_path.exists():
                self.stderr.write(
                    self.style.ERROR(
                        "Cannot skip graph — timetrix_graph.gpickle not found."
                    )
                )
                return
            self.stdout.write("Skipping graph build (--skip-graph).")
        else:
            self.stdout.write("Phase 1/3: Building graph...")
            graph_builder.main()
            self.stdout.write(self.style.SUCCESS("  Graph built."))

        # Phase 2: GNN
        if options["skip_gnn"]:
            embed_path = TRAINED_DIR / "node_embeddings.pkl"
            if not embed_path.exists():
                self.stderr.write(
                    self.style.ERROR(
                        "Cannot skip GNN — node_embeddings.pkl not found."
                    )
                )
                return
            self.stdout.write("Skipping GNN training (--skip-gnn).")
        else:
            self.stdout.write("Phase 2/3: Training GNN...")
            gnn_model.main()
            self.stdout.write(self.style.SUCCESS("  GNN trained."))

        # Phase 3: RF
        self.stdout.write("Phase 3/3: Training Random Forest...")
        random_forest_model.main()
        self.stdout.write(self.style.SUCCESS("  RF trained."))

        self.stdout.write(self.style.SUCCESS("\nFull pipeline complete."))
