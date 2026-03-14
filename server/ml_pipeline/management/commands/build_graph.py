# server/ml_pipeline/management/commands/build_graph.py

from django.core.management.base import BaseCommand
from ml_pipeline import graph_builder

class Command(BaseCommand):
    help = "Build the timetable graph from CSV data"

    def handle(self, *args, **options):
        self.stdout.write("Building graph...")
        G, features, meta, stats = graph_builder.main()
        self.stdout.write(
            self.style.SUCCESS(
                f"Done. {stats['total_nodes']} nodes, "
                f"{stats['total_edges']} edges"
            )
        )
