from django.db import migrations, models
import django.db.models.deletion


def copiar_periodos_desde_actividad(apps, schema_editor):
    AtencionSocial = apps.get_model('admin_demo_app', 'AtencionSocial')
    Compromiso = apps.get_model('admin_demo_app', 'Compromiso')
    for atencion in AtencionSocial.objects.filter(actividad__isnull=False, periodo__isnull=True).select_related('actividad'):
        atencion.periodo_id = atencion.actividad.periodo_id
        atencion.save(update_fields=['periodo'])
    for compromiso in Compromiso.objects.filter(actividad_origen__isnull=False, periodo__isnull=True).select_related('actividad_origen'):
        compromiso.periodo_id = compromiso.actividad_origen.periodo_id
        compromiso.save(update_fields=['periodo'])


class Migration(migrations.Migration):
    dependencies = [
        ('admin_demo_app', '0016_organizacionjjvv_directiva_usuarios'),
    ]

    operations = [
        migrations.AddField(
            model_name='atencionsocial',
            name='periodo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='atenciones_sociales', to='admin_demo_app.periodo'),
        ),
        migrations.AddField(
            model_name='compromiso',
            name='periodo',
            field=models.ForeignKey(blank=True, null=True, on_delete=django.db.models.deletion.RESTRICT, related_name='compromisos', to='admin_demo_app.periodo'),
        ),
        migrations.RunPython(copiar_periodos_desde_actividad, migrations.RunPython.noop),
    ]