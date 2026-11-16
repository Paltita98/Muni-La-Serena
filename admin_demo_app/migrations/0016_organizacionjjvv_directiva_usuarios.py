from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    dependencies = [
        ('admin_demo_app', '0015_cartadelegacion'),
    ]

    operations = [
        migrations.AddField(
            model_name='organizacionjjvv',
            name='presidente_usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='organizaciones_presididas', to='admin_demo_app.usuario'),
        ),
        migrations.AddField(
            model_name='organizacionjjvv',
            name='tesorero_usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='organizaciones_tesoreria', to='admin_demo_app.usuario'),
        ),
        migrations.AddField(
            model_name='organizacionjjvv',
            name='secretario_usuario',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='organizaciones_secretaria', to='admin_demo_app.usuario'),
        ),
    ]
