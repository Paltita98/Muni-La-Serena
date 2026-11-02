from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admin_demo_app', '0009_protect_delegacion_with_assigned_users'),
    ]

    operations = [
        migrations.AddField(
            model_name='personausuaria',
            name='rut',
            field=models.CharField(blank=True, max_length=12, null=True, unique=True),
        ),
        migrations.AddField(
            model_name='personausuaria',
            name='nombre',
            field=models.CharField(blank=True, max_length=150),
        ),
        migrations.AddField(
            model_name='personausuaria',
            name='telefono',
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.AddField(
            model_name='compromiso',
            name='persona',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.SET_NULL,
                related_name='compromisos',
                to='admin_demo_app.personausuaria',
            ),
        ),
    ]