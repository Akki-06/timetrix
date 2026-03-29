from django.core.management.base import BaseCommand
from ml_pipeline import random_forest_model


class Command(BaseCommand):
    help = "Train the Random Forest ensemble (requires node_embeddings.pkl)"

    def handle(self, *args, **options):
        self.stdout.write(
            "Training RF model (node_embeddings.pkl must exist — "
            "run train_gnn first if needed)..."
        )
        random_forest_model.main()
        self.stdout.write(self.style.SUCCESS("Done. RF model saved."))
