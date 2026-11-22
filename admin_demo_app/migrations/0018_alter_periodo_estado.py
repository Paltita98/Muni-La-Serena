from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_demo_app', '0017_periodo_en_atencion_y_compromiso'),
    ]

    operations = [
        migrations.AlterField(
            model_name='periodo',
            name='estado',
            field=models.CharField(choices=[('abierto', 'Abierto'), ('cerrado', 'Cerrado')], default='cerrado', max_length=10),
        ),
    ]
