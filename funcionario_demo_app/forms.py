from django import forms
from PIL import Image, UnidentifiedImageError
from django.db.models import Q
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
    Validacion,
)


class ImageEvidenceField(forms.FileField):
    def __init__(self, *args, **kwargs):
        attrs = kwargs.pop('widget_attrs', {})
        kwargs.setdefault('widget', forms.ClearableFileInput(attrs={
            'accept': 'image/jpeg,image/png,image/gif,image/webp,image/bmp',
            **attrs,
        }))
        super().__init__(*args, **kwargs)

    def clean(self, data, initial=None):
        uploaded_file = super().clean(data, initial)
        if not uploaded_file:
            return uploaded_file
        try:
            with Image.open(uploaded_file) as image:
                if image.format not in {'JPEG', 'PNG', 'GIF', 'WEBP', 'BMP'}:
                    raise forms.ValidationError('El archivo debe ser una imagen JPG, PNG, GIF, WEBP o BMP.')
                image.verify()
        except forms.ValidationError:
            raise
        except (UnidentifiedImageError, OSError, ValueError, Image.DecompressionBombError) as error:
            raise forms.ValidationError('El archivo no es una imagen válida.') from error
        finally:
            uploaded_file.seek(0)
        return uploaded_file


class EvidenciaForm(forms.Form):
    archivo = ImageEvidenceField(label="Imagen de evidencia")


class VerificacionEvidenciaForm(forms.Form):
    decision = forms.ChoiceField(
        label='Decisión',
        choices=(('aprobada', 'Aprobar evidencia'), ('rechazada', 'Rechazar y solicitar corrección')),
    )
    observacion = forms.CharField(
        label='Observación para el funcionario',
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={'rows': 3}),
    )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('decision') == 'rechazada' and not cleaned_data.get('observacion', '').strip():
            self.add_error('observacion', 'Describe qué debe corregir el funcionario antes de devolver la evidencia.')
        return cleaned_data


class ActividadForm(forms.ModelForm):
    evidencia = ImageEvidenceField(required=False, label="Adjuntar imagen de evidencia")

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


class SubatencionSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, 'instance', None)
        if instance:
            option['attrs']['data-tipo'] = str(instance.padre_id or '')
        return option


class AtencionSocialForm(forms.Form):
    solicitante = forms.CharField(label="Solicitante", max_length=150)
    referencia_anonima = forms.CharField(
        label="Código anónimo de la persona",
        max_length=40,
        help_text="Usa el mismo código para agregar gestiones a una persona ya registrada.",
        widget=forms.TextInput(attrs={"autocomplete": "off", "placeholder": "Ej.: CASO-001"}),
    )
    catalogo_tipo = forms.ModelChoiceField(label="Tipo de atención", queryset=CatalogoTipo.objects.none())
    catalogo_subtipo = forms.ModelChoiceField(
        label="Subatención", queryset=CatalogoTipo.objects.none(), required=False,
        widget=SubatencionSelect,
    )
    delegacion = forms.ModelChoiceField(label="Delegación", queryset=Delegacion.objects.none())
    descripcion = forms.CharField(label="Descripción", widget=forms.Textarea(attrs={"rows": 4}))
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
            estado="activo", categoria="atencion", padre__isnull=True,
        ).order_by("nombre")
        tipo_id = self.data.get('catalogo_tipo') if self.is_bound else None
        subtipos = CatalogoTipo.objects.filter(estado='activo', categoria='subatencion')
        if tipo_id:
            subtipos = subtipos.filter(padre_id=tipo_id)
        self.fields['catalogo_subtipo'].queryset = subtipos.order_by('nombre')
        delegaciones = Delegacion.objects.filter(estado='activa')
        if funcionario:
            alcance = Q(pk=getattr(funcionario, 'delegacion_id', None)) if getattr(funcionario, 'delegacion_id', None) else Q()
            autorizadas = getattr(funcionario, 'delegaciones_autorizadas', None)
            if autorizadas:
                alcance |= Q(pk__in=autorizadas.values('pk'))
            delegaciones = delegaciones.filter(alcance) if alcance.children else delegaciones.none()
        self.fields['delegacion'].queryset = delegaciones.order_by('nombre')
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
        tipo = cleaned_data.get('catalogo_tipo')
        subtipo = cleaned_data.get('catalogo_subtipo')
        if subtipo and tipo and subtipo.padre_id != tipo.pk:
            self.add_error('catalogo_subtipo', 'La subatención debe corresponder al tipo seleccionado.')
        return cleaned_data

    def save(self):
        persona, _ = PersonaUsuaria.objects.get_or_create(
            referencia_anonima=self.cleaned_data["referencia_anonima"].strip(),
        )
        return AtencionSocial.objects.create(
            persona=persona,
            solicitante=self.cleaned_data['solicitante'],
            descripcion=self.cleaned_data['descripcion'],
            delegacion=self.cleaned_data['delegacion'],
            catalogo_tipo=self.cleaned_data["catalogo_tipo"],
            catalogo_subtipo=self.cleaned_data['catalogo_subtipo'],
            funcionario=self.funcionario,
            orden_gestion=self.cleaned_data["orden_gestion"],
            fecha=self.cleaned_data["fecha"],
            resultado=self.cleaned_data["resultado"],
            actividad=self.cleaned_data["actividad"],
        )
