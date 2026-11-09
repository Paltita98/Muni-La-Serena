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
    OrganizacionJJVV,
    Periodo,
    PersonaUsuaria,
    Usuario,
    Validacion,
)
from admin_demo_app.validators import validate_chilean_rut


class PersonaSolicitanteFields:
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['persona'].queryset = PersonaUsuaria.objects.all()
        for field_name in ('nuevo_rut', 'nuevo_nombre', 'nuevo_telefono'):
            self.fields[field_name].widget.attrs['class'] = (
                'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm '
                'focus:outline-none focus:ring-2 focus:ring-red-500'
            )

    def clean(self):
        cleaned_data = super().clean()
        if cleaned_data.get('persona'):
            return cleaned_data

        rut = cleaned_data.get('nuevo_rut', '').strip().replace('.', '').upper()
        nombre = cleaned_data.get('nuevo_nombre', '').strip()
        telefono = cleaned_data.get('nuevo_telefono', '').strip()
        if not rut:
            self.add_error('nuevo_rut', 'Ingresa el RUT o selecciona una persona existente.')
        else:
            try:
                validate_chilean_rut(rut)
            except forms.ValidationError as error:
                self.add_error('nuevo_rut', error)
            if PersonaUsuaria.objects.filter(rut=rut).exists():
                self.add_error('nuevo_rut', 'Este RUT ya está registrado. Búscalo y selecciónalo.')
        if not nombre:
            self.add_error('nuevo_nombre', 'Ingresa el nombre de la persona.')
        if not telefono:
            self.add_error('nuevo_telefono', 'Ingresa el teléfono de la persona.')
        cleaned_data['nuevo_rut'] = rut
        cleaned_data['nuevo_nombre'] = nombre
        cleaned_data['nuevo_telefono'] = telefono
        return cleaned_data

    def obtener_persona(self):
        persona = self.cleaned_data.get('persona')
        if persona:
            return persona
        return PersonaUsuaria.crear_con_referencia_incremental(
            rut=self.cleaned_data['nuevo_rut'],
            nombre=self.cleaned_data['nuevo_nombre'],
            telefono=self.cleaned_data['nuevo_telefono'],
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


class OrganizacionJJVVForm(forms.ModelForm):
    class Meta:
        model = OrganizacionJJVV
        fields = (
            'organizaciones',
            'domicilio_legal',
            'territorio_deleg',
            'socios_activos',
            'fecha_constitucion',
            'n_reg_pj',
            'fecha_inscripcion_reg',
            'reg_dir_n',
            'presidente_n',
            'tesorero_n',
            'secretario_n',
        )
        labels = {
            'organizaciones': 'Nombre de la organización',
            'domicilio_legal': 'Domicilio legal',
            'territorio_deleg': 'Territorio o delegación',
            'socios_activos': 'Socios activos',
            'fecha_constitucion': 'Fecha de constitución',
            'n_reg_pj': 'Número de registro de personalidad jurídica',
            'fecha_inscripcion_reg': 'Fecha de inscripción en el registro',
            'reg_dir_n': 'Número de registro de directorio',
            'presidente_n': 'Presidente',
            'tesorero_n': 'Tesorero',
            'secretario_n': 'Secretario',
        }
        widgets = {
            'organizaciones': forms.TextInput(attrs={'autocomplete': 'organization'}),
            'domicilio_legal': forms.TextInput(),
            'territorio_deleg': forms.TextInput(),
            'socios_activos': forms.NumberInput(attrs={'min': 0, 'step': 1}),
            'fecha_constitucion': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'n_reg_pj': forms.TextInput(),
            'fecha_inscripcion_reg': forms.DateInput(format='%Y-%m-%d', attrs={'type': 'date'}),
            'reg_dir_n': forms.TextInput(),
            'presidente_n': forms.TextInput(attrs={'autocomplete': 'name'}),
            'tesorero_n': forms.TextInput(attrs={'autocomplete': 'name'}),
            'secretario_n': forms.TextInput(attrs={'autocomplete': 'name'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs['class'] = (
                'w-full rounded-md border border-gray-300 bg-white px-3 py-2 text-sm '
                'focus:border-emerald-700 focus:outline-none focus:ring-2 focus:ring-emerald-100'
            )

    def clean(self):
        cleaned_data = super().clean()
        fecha_constitucion = cleaned_data.get('fecha_constitucion')
        fecha_inscripcion = cleaned_data.get('fecha_inscripcion_reg')
        if fecha_constitucion and fecha_inscripcion and fecha_inscripcion < fecha_constitucion:
            self.add_error('fecha_inscripcion_reg', 'La inscripción no puede ser anterior a la constitución.')
        return cleaned_data


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


class CompromisoForm(PersonaSolicitanteFields, forms.ModelForm):
    persona = forms.ModelChoiceField(
        label='Persona seleccionada', queryset=PersonaUsuaria.objects.none(),
        required=False, widget=forms.HiddenInput,
    )
    nuevo_rut = forms.CharField(label='RUT', max_length=12, required=False)
    nuevo_nombre = forms.CharField(label='Nombre completo', max_length=150, required=False)
    nuevo_telefono = forms.CharField(label='Teléfono', max_length=20, required=False)

    class Meta:
        model = Compromiso
        fields = (
            "fecha_comprometida",
            "delegacion",
            "persona",
            "territorio",
            "observacion",
        )
        labels = {
            "fecha_comprometida": "Fecha comprometida",
            "delegacion": "Delegación",
            "persona": "Persona solicitante",
            "territorio": "Territorio o sector",
            "observacion": "Descripción del compromiso",
        }
        widgets = {
            "fecha_comprometida": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, funcionario=None, **kwargs):
        super().__init__(*args, **kwargs)
        delegaciones = Delegacion.objects.filter(estado="activa")
        if funcionario and funcionario.delegacion_id:
            delegaciones = delegaciones.filter(pk=funcionario.delegacion_id)
        else:
            delegaciones = Delegacion.objects.none()
        self.fields["delegacion"].queryset = delegaciones.order_by("nombre")


class DelegadoCompromisoForm(forms.ModelForm):
    class Meta:
        model = Compromiso
        fields = (
            "fecha_comprometida",
            "responsable",
            "solicitante",
            "territorio",
            "observacion",
        )
        labels = {
            "fecha_comprometida": "Fecha comprometida",
            "responsable": "Funcionario responsable",
            "solicitante": "Solicitante (vecino/institución)",
            "territorio": "Territorio o sector",
            "observacion": "Descripción del compromiso",
        }
        widgets = {
            "fecha_comprometida": forms.DateInput(attrs={"type": "date"}),
            "observacion": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, delegacion=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.delegacion = delegacion
        if self.instance.pk:
            self.fields.pop("fecha_comprometida")
        self.fields["responsable"].queryset = (
            Usuario.objects.filter(delegacion=delegacion, estado="activo")
            .order_by("apellidos", "nombres")
            if delegacion else Usuario.objects.none()
        )
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500",
            )


class CompromisoEstadoForm(forms.Form):
    estado = forms.ChoiceField(label="Nuevo estado")
    observacion = forms.CharField(
        label="Comentario de seguimiento",
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, estados_permitidos=(), **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["estado"].choices = estados_permitidos
        for field in self.fields.values():
            field.widget.attrs.setdefault(
                "class",
                "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-500",
            )

    def save(self, commit=True):
        compromiso = super().save(commit=False)
        persona = self.obtener_persona()
        compromiso.persona = persona
        compromiso.solicitante = persona.nombre or persona.referencia_anonima
        if commit:
            compromiso.save()
            self.save_m2m()
        return compromiso


class SubatencionSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        instance = getattr(value, 'instance', None)
        if instance:
            option['attrs']['data-tipo'] = str(instance.padre_id or '')
        return option


class AtencionSocialForm(PersonaSolicitanteFields, forms.Form):
    persona = forms.ModelChoiceField(
        label='Persona seleccionada', queryset=PersonaUsuaria.objects.none(),
        required=False, widget=forms.HiddenInput,
    )
    nuevo_rut = forms.CharField(label='RUT', max_length=12, required=False)
    nuevo_nombre = forms.CharField(label='Nombre completo', max_length=150, required=False)
    nuevo_telefono = forms.CharField(label='Teléfono', max_length=20, required=False)
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
        persona = cleaned_data.get('persona')
        orden = cleaned_data.get("orden_gestion")
        if persona and orden and AtencionSocial.objects.filter(persona=persona, orden_gestion=orden).exists():
            self.add_error("orden_gestion", "Esta persona ya tiene registrada esa gestión.")
        if not self.funcionario:
            self.add_error(None, "No hay un funcionario activo para registrar la atención.")
        tipo = cleaned_data.get('catalogo_tipo')
        subtipo = cleaned_data.get('catalogo_subtipo')
        if subtipo and tipo and subtipo.padre_id != tipo.pk:
            self.add_error('catalogo_subtipo', 'La subatención debe corresponder al tipo seleccionado.')
        return cleaned_data

    def save(self):
        persona = self.obtener_persona()
        return AtencionSocial.objects.create(
            persona=persona,
            solicitante=persona.nombre or persona.referencia_anonima,
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
