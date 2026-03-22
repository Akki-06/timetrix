from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('academics', '0004_room_timetableversion_workingday_and_more'),
    ]

    operations = [
        migrations.DeleteModel(
            name='Room',
        ),
    ]
