"""
Delete orphaned editor drafts older than 24 hours.

Usage:
    python manage.py editor_cleanup

Can be run as a cron job or called on server startup.
"""
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from scheduler.models import Timetable


class Command(BaseCommand):
    help = "Delete orphaned editor draft timetables older than 24 hours."

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-age-hours",
            type=int,
            default=24,
            help="Delete drafts older than this many hours (default: 24).",
        )

    def handle(self, *args, **options):
        max_age = timedelta(hours=options["max_age_hours"])
        cutoff = timezone.now() - max_age

        old_drafts = Timetable.objects.filter(is_draft=True, created_at__lt=cutoff)
        count = old_drafts.count()

        if count == 0:
            self.stdout.write(self.style.SUCCESS("No orphaned drafts found."))
            return

        old_drafts.delete()  # CASCADE deletes all LectureAllocations too
        self.stdout.write(
            self.style.SUCCESS(f"Deleted {count} orphaned draft(s) older than {options['max_age_hours']}h.")
        )
