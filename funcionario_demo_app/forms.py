from django import forms
from django.utils import timezone

from admin_demo_app.models import (
    Actividad,
    AtencionSocial,
    CatalogoTipo,
    Compromiso,
    Delegacion,
    ItemMedicion,
    Periodo,
    PersonaUsuaria,
)


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
        if funcionario and funcionario.cargo_id:
            self.fields["item"].queryset = ItemMedicion.objects.filter(
                cargo=funcionario.cargo,
                estado="activo",
            ).order_by("nombre")
        else:
            self.fields["item"].queryset = ItemMedicion.objects.filter(estado="activo").order_by("nombre")

    def clean(self):
        cleaned_data = super().clean()
        if not self.funcionario:
            self.add_error(None, "No existe un funcionario activo para registrar la actividad.")
        if not Periodo.objects.filter(estado="abierto").exists():
            self.add_error(None, "No hay un período de medición abierto. Cree o abra un período antes de registrar actividades.")
        return cleaned_data


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


class AtencionSocialForm(forms.Form):
    referencia_anonima = forms.CharField(
        label="Código anónimo de la persona",
        max_length=40,
        help_text="Usa el mismo código para agregar gestiones a una persona ya registrada.",
        widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Ej.: CASO-001"}),
    )
    catalogo_tipo = forms.ModelChoiceField(label="Tipo de atención", queryset=CatalogoTipo.objects.none())
    orden_gestion = forms.TypedChoiceField(
        label="Número de gestión",
        choices=((1, "1. Primera gestión"), (2, "2. Segunda gestión"), (3, "3. Tercera gestión")),
        coerce=int,
    )
    fecha = forms.DateField(
        label="Fecha de atención",
        initial=timezone.localdate,
        widget=forms.DateInput(attrs={"type": "date"}),
    )
    resultado = forms.CharField(
        label="Resultado o acuerdos",
        max_length=255,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )
    actividad = forms.ModelChoiceField(
        label="Actividad relacionada (opcional)",
        queryset=Actividad.objects.none(),
        required=False,
        empty_label="Sin actividad relacionada",
    )

    def __init__(self, *args, funcionario=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.funcionario = funcionario
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-red-500",
            )
        self.fields["catalogo_tipo"].queryset = CatalogoTipo.objects.filter(
            estado="activo",
            categoria__in=("atencion", "subatencion", "servicio"),
        ).order_by("nombre")
        self.fields["actividad"].queryset = Actividad.objects.filter(
            funcionario=funcionario,
        ).order_by("-fecha_actividad") if funcionario else Actividad.objects.none()

    def clean(self):
        cleaned_data = super().clean()
        referencia = cleaned_data.get("referencia_anonima", "").strip()
        orden = cleaned_data.get("orden_gestion")
        if referencia and orden:
            persona = PersonaUsuaria.objects.filter(referencia_anonima=referencia).first()
            if persona and AtencionSocial.objects.filter(persona=persona, orden_gestion=orden).exists():
                self.add_error("orden_gestion", "Esta persona ya tiene registrada esa gestión.")
        if not self.funcionario:
            self.add_error(None, "No hay un funcionario activo para registrar la atención.")
        return cleaned_data

    def save(self):
        persona, _ = PersonaUsuaria.objects.get_or_create(
            referencia_anonima=self.cleaned_data["referencia_anonima"].strip(),
        )
        return AtencionSocial.objects.create(
            persona=persona,
            catalogo_tipo=self.cleaned_data["catalogo_tipo"],
            funcionario=self.funcionario,
            orden_gestion=self.cleaned_data["orden_gestion"],
            fecha=self.cleaned_data["fecha"],
            resultado=self.cleaned_data["resultado"],
            actividad=self.cleaned_data["actividad"],
        )
