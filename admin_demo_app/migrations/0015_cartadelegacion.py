import django.db.models.deletion
import django.utils.timezone
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('admin_demo_app', '0014_organizacionjjvv_delegacion'),
    ]

    operations = [
        migrations.CreateModel(
            name='CartaDelegacion',
            fields=[
                ('id', models.BigAutoField(db_column='id_carta', primary_key=True, serialize=False)),
                ('folio', models.CharField(max_length=50)),
                ('fecha_emision', models.DateField(default=django.utils.timezone.localdate)),
                ('destinatario', models.CharField(max_length=150)),
                ('institucion', models.CharField(blank=True, max_length=150)),
                ('asunto', models.CharField(max_length=255)),
                ('contenido', models.TextField(blank=True)),
                ('estado', models.CharField(choices=[('pendiente', 'Pendiente'), ('enviada', 'Enviada'), ('respondida', 'Respondida'), ('anulada', 'Anulada')], default='pendiente', max_length=12)),
                ('fecha_envio', models.DateField(blank=True, null=True)),
                ('observaciones', models.TextField(blank=True)),
                ('fecha_registro', models.DateTimeField(auto_now_add=True)),
                ('delegacion', models.ForeignKey(db_column='id_delegacion', on_delete=django.db.models.deletion.RESTRICT, related_name='cartas', to='admin_demo_app.delegacion')),
                ('registrada_por', models.ForeignKey(blank=True, db_column='id_usuario', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='cartas_registradas', to='admin_demo_app.usuario')),
            ],
            options={
                'verbose_name': 'Carta de delegación',
                'verbose_name_plural': 'Cartas de delegación',
                'db_table': 'carta_delegacion',
                'ordering': ('-fecha_emision', '-id'),
            },
        ),
        migrations.AddConstraint(
            model_name='cartadelegacion',
            constraint=models.UniqueConstraint(fields=('delegacion', 'folio'), name='carta_delegacion_folio_unico'),
        ),
    ]