from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_demo_app', '0007_meta_unidad_heredada'),
    ]

    operations = [
        migrations.AddField(
            model_name='usuario',
            name='debe_cambiar_password',
            field=models.BooleanField(default=False),
        ),
        migrations.AlterField(
            model_name='delegacion',
            name='comuna',
            field=models.CharField(blank=True, default='La Serena', max_length=100),
        ),
    ]