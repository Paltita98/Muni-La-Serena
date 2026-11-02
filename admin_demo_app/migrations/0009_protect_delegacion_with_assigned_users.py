from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('admin_demo_app', '0008_usuario_debe_cambiar_password_delegacion_comuna_default'),
    ]

    operations = [
        migrations.AlterField(
            model_name='usuario',
            name='delegacion',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                to='admin_demo_app.delegacion',
            ),
        ),
    ]