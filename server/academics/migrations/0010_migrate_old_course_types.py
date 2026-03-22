from django.db import migrations


OLD_TO_NEW = {
    "THEORY": "PC",
    "LAB": "PR",
    "ELECTIVE": "PE",
    "COMPULSORY": "PC",
    "SEMINAR": "AEC",
    "PROJECT": "PRJ",
}


def forwards(apps, schema_editor):
    Course = apps.get_model("academics", "Course")
    for old, new in OLD_TO_NEW.items():
        Course.objects.filter(course_type=old).update(course_type=new)


def backwards(apps, schema_editor):
    pass  # non-reversible


class Migration(migrations.Migration):

    dependencies = [
        ("academics", "0009_update_course_type_choices"),
    ]

    operations = [
        migrations.RunPython(forwards, backwards),
    ]
