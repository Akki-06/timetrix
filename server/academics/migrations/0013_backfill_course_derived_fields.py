from django.db import migrations


def backfill(apps, schema_editor):
    Course = apps.get_model("academics", "Course")
    _NOT_SCHEDULED     = {"DIS", "INT", "RND"}
    _CONSECUTIVE_TYPES = {"PR", "PRJ"}
    _LAB_ROOM_TYPES    = {"PR"}
    _priority = {
        "PR": 5,
        "PC": 4, "BSC": 4, "ESC": 4,
        "PE": 3, "OE": 3, "HUM": 3,
        "LS": 2, "VAM": 2, "AEC": 2,
    }
    for course in Course.objects.all():
        ct = course.course_type
        if ct in _CONSECUTIVE_TYPES:
            lectures = 1
        elif ct in _NOT_SCHEDULED:
            lectures = 0
        else:
            lectures = min(course.credits, 4)
        course.min_weekly_lectures        = lectures
        course.max_weekly_lectures        = lectures
        course.requires_lab_room          = (ct in _LAB_ROOM_TYPES)
        course.requires_consecutive_slots = (ct in _CONSECUTIVE_TYPES)
        course.priority = _priority.get(ct, 1)
        course.save()


class Migration(migrations.Migration):
    dependencies = [("academics", "0012_add_program_specialization_and_duration")]
    operations = [migrations.RunPython(backfill, migrations.RunPython.noop)]
