from django import forms
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.contrib.auth.hashers import make_password

from .validators import validate_chilean_rut
from .models import Cargo, CatalogoTipo, Delegacion, ItemMedicion, Meta, Periodo, Rol, Usuario


class MetaItemSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(name, value, label, selected, index, subindex, attrs)
        item = getattr(value, 'instance', None)
        if item:
            option['attrs']['data-unidad'] = item.unidad or ''
            option['attrs']['data-cargo'] = item.cargo.nombre
        return option


class CatalogoTipoForm(forms.ModelForm):
    class Meta:
        model = CatalogoTipo
        fields = ('codigo', 'nombre', 'descripcion', 'categoria', 'padre', 'area', 'estado')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['categoria'].choices = (
            ('atencion', 'Tipo de Atención'),
            ('subatencion', 'Sub Atención'),
        )
        self.fields['padre'].queryset = CatalogoTipo.objects.filter(
            categoria='atencion', estado='activo',
        ).order_by('nombre')

    def clean(self):
        cleaned_data = super().clean()
        categoria = cleaned_data.get('categoria')
        padre = cleaned_data.get('padre')
        if categoria == 'subatencion' and not padre:
            self.add_error('padre', 'Selecciona el Tipo de Atención asociado.')
        if categoria == 'atencion' and padre:
            self.add_error('padre', 'Un Tipo de Atención no puede depender de otro tipo.')
        return cleaned_data


class DelegacionForm(forms.ModelForm):
    class Meta:
        model = Delegacion
        fields = ('codigo', 'nombre', 'direccion', 'comuna', 'ambito', 'responsable', 'estado')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for name in ('codigo', 'direccion', 'comuna'):
            self.fields[name].required = True


class RolForm(forms.ModelForm):
    permisos = forms.CharField(required=False, widget=forms.Textarea(attrs={'rows': 4}), help_text='Un permiso por línea.')

    class Meta:
        model = Rol
        fields = ('nombre', 'descripcion', 'permisos', 'alcance_autorizado')

    def clean_permisos(self):
        return [line.strip() for line in self.cleaned_data['permisos'].splitlines() if line.strip()]


class ItemMedicionForm(forms.ModelForm):
    class Meta:
        model = ItemMedicion
        fields = ('codigo', 'nombre', 'descripcion', 'cargo', 'tipo', 'unidad', 'formula_desc', 'estado')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['codigo'].required = True
        self.fields['descripcion'].required = True


class MetaForm(forms.ModelForm):
    cargo_mostrado = forms.CharField(
        label='Cargo del ítem',
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-100'}),
    )
    unidad_mostrada = forms.CharField(
        label='Unidad del ítem',
        required=False,
        disabled=True,
        widget=forms.TextInput(attrs={'class': 'w-full border border-gray-300 rounded-lg px-3 py-2 text-sm bg-gray-100'}),
    )

    class Meta:
        model = Meta
        fields = (
            'item', 'cargo_mostrado', 'unidad_mostrada', 'funcionario', 'periodo', 'valor_objetivo',
            'ponderador_pct', 'umbral_minimo_pct', 'maximo_computable_pct', 'vigente',
        )
        widgets = {'item': MetaItemSelect}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ItemMedicion.objects.filter(estado='activo').select_related('cargo').order_by('nombre')
        self.fields['item'].help_text = 'El cargo y la unidad se heredan del ítem seleccionado.'
        self.fields['funcionario'].queryset = Usuario.objects.filter(estado='activo').order_by('nombres', 'apellidos')
        self.fields['periodo'].queryset = Periodo.objects.order_by('-fecha_inicio')
        self.fields['funcionario'].required = False
        self.fields['cargo_mostrado'].initial = self.instance.item.cargo.nombre if self.instance.pk else ''
        self.fields['unidad_mostrada'].initial = self.instance.item.unidad if self.instance.pk else ''

    def clean(self):
        cleaned_data = super().clean()
        item = cleaned_data.get('item')
        funcionario = cleaned_data.get('funcionario')
        if item and funcionario and funcionario.cargo_id != item.cargo_id:
            self.add_error('funcionario', 'El funcionario debe pertenecer al cargo del ítem seleccionado.')
        if item:
            self.instance.cargo = item.cargo
        return cleaned_data


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={
            "autocomplete": "new-password",
            "minlength": "8",
            "pattern": "(?=.*[A-Z])(?=.*[^A-Za-z0-9]).{8,}",
            "title": "Usa al menos 8 caracteres, una mayúscula y un carácter especial.",
        }),
        help_text="Déjala vacía al editar para conservar la contraseña actual.",
    )

    class Meta:
        model = Usuario
        fields = (
            "identificador_inst",
            "nombres",
            "apellidos",
            "email",
            "password",
            "cargo",
            "delegacion",
            "delegaciones_autorizadas",
            "roles",
            "estado",
        )
        labels = {
            "identificador_inst": "RUT / Identificador",
            "nombres": "Nombres",
            "apellidos": "Apellidos",
            "email": "Correo institucional",
            "cargo": "Cargo",
            "delegacion": "Delegación",
            "delegaciones_autorizadas": "Delegaciones autorizadas",
            "roles": "Roles",
            "estado": "Estado",
        }
        widgets = {
            "identificador_inst": forms.TextInput(attrs={
                "class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm",
                "pattern": "[0-9]{7,8}-[0-9kK]",
                "placeholder": "19864005-0",
                "title": "Ingresa el RUT sin puntos y con guion, por ejemplo 19864005-0.",
            }),
            "nombres": forms.TextInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "apellidos": forms.TextInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "email": forms.EmailInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "cargo": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "delegacion": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "delegaciones_autorizadas": forms.CheckboxSelectMultiple,
            "estado": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "roles": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].queryset = Cargo.objects.filter(estado="activo").order_by("nombre")
        self.fields["delegacion"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
        self.fields["delegaciones_autorizadas"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
        self.fields["roles"].queryset = Rol.objects.order_by("nombre")
        self.fields["cargo"].required = True
        self.fields["delegacion"].required = True
        self.fields["roles"].required = True

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.instance.pk and not password:
            raise forms.ValidationError("La contraseña es obligatoria al crear un usuario.")
        if password:
            try:
                validate_password(password, user=self.instance if self.instance.pk else None)
            except ValidationError as error:
                raise forms.ValidationError(error.messages) from error
        return password

    def clean_identificador_inst(self):
        identificador = self.cleaned_data["identificador_inst"].strip().replace('.', '').upper()
        validate_chilean_rut(identificador)
        return identificador

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            usuario.password_hash = make_password(password)
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario
