from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admin_demo_app', '0018_alter_periodo_estado'),
    ]

    operations = [
        migrations.AddField(
            model_name='actividad',
            name='origen_tipo',
            field=models.CharField(
                choices=[('personal', 'Personal'), ('organizacion', 'Por organización')],
                default='personal',
                max_length=15,
            ),
        ),
        migrations.AddField(
            model_name='actividad',
            name='organizacion',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='actividades',
                to='admin_demo_app.organizacionjjvv',
            ),
        ),
    ]