from django import forms

from admin_demo_app.models import Actividad, Compromiso, Delegacion, ItemMedicion, Periodo


class EvidenciaForm(forms.Form):
    archivo = forms.FileField(label="Archivo de evidencia")


class ActividadForm(forms.ModelForm):
    evidencia = forms.FileField(required=False, label="Adjuntar evidencia")

    class Meta:
        model = Actividad
        fields = (
            "fecha_actividad",
            "item",
            "accion",
            "descripcion",
            "contacto_nombre",
            "contacto_telefono",
        )
        labels = {
            "fecha_actividad": "Fecha de la actividad",
            "item": "Ítem a medir",
            "accion": "Tipo de acción",
            "descripcion": "Descripción detallada",
            "contacto_nombre": "Nombre completo",
            "contacto_telefono": "Teléfono",
        }
        widgets = {
            "fecha_actividad": forms.DateInput(attrs={"type": "date"}),
            "accion": forms.TextInput(),
            "descripcion": forms.Textarea(attrs={"rows": 3}),
        }

    def __init__(self, *args, funcionario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.funcionario = funcionario
        if not funcionario:
            self.add_error(None, "No existe un funcionario activo para registrar la actividad.")
        if not Periodo.objects.filter(estado="abierto").exists():
            self.add_error(None, "No hay un período de medición abierto. Cree o abra un período antes de registrar actividades.")
        if funcionario and funcionario.cargo_id:
            self.fields["item"].queryset = ItemMedicion.objects.filter(
                cargo=funcionario.cargo,
                estado="activo",
            ).order_by("nombre")
        else:
            self.fields["item"].queryset = ItemMedicion.objects.filter(estado="activo").order_by("nombre")


class CompromisoForm(forms.ModelForm):
    class Meta:
        model = Compromiso
        fields = (
            "fecha_comprometida",
            "delegacion",
            "solicitante",
            "territorio",
            "observacion",
        )
        labels = {
            "fecha_comprometida": "Fecha comprometida",
            "delegacion": "Delegación",
            "solicitante": "Solicitante (vecino/institución)",
            "territorio": "Territorio o sector",
            "observacion": "Descripción del compromiso",
        }
        widgets = {
            "fecha_comprometida": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["delegacion"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
