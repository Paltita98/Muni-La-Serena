from django import forms
from django.contrib.auth.hashers import make_password

from .models import Cargo, CatalogoTipo, Delegacion, ItemMedicion, Meta, Periodo, Rol, Usuario


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
    class Meta:
        model = Meta
        fields = (
            'item', 'cargo', 'funcionario', 'periodo', 'valor_objetivo', 'unidad',
            'ponderador_pct', 'umbral_minimo_pct', 'maximo_computable_pct', 'vigente',
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['item'].queryset = ItemMedicion.objects.filter(estado='activo').order_by('nombre')
        self.fields['cargo'].queryset = Cargo.objects.filter(estado='activo').order_by('nombre')
        self.fields['funcionario'].queryset = Usuario.objects.filter(estado='activo').order_by('nombres', 'apellidos')
        self.fields['periodo'].queryset = Periodo.objects.order_by('-fecha_inicio')
        self.fields['cargo'].required = False
        self.fields['funcionario'].required = False

    def clean(self):
        cleaned_data = super().clean()
        if not cleaned_data.get('cargo') and not cleaned_data.get('funcionario'):
            raise forms.ValidationError('Asigna la meta a un cargo o a un funcionario.')
        return cleaned_data


class DelegacionForm(forms.ModelForm):
    class Meta:
        model = Delegacion
        fields = ('codigo', 'nombre', 'direccion', 'comuna', 'ambito', 'responsable', 'estado')


class RolForm(forms.ModelForm):
    class Meta:
        model = Rol
        fields = ('nombre', 'descripcion', 'permisos', 'alcance_autorizado')


class ItemMedicionForm(forms.ModelForm):
    class Meta:
        model = ItemMedicion
        fields = ('codigo', 'nombre', 'descripcion', 'cargo', 'tipo', 'unidad', 'formula_desc', 'estado')


class UsuarioForm(forms.ModelForm):
    password = forms.CharField(
        label="Contraseña",
        required=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "new-password"}),
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
            "delegaciones_autorizadas": "Delegaciones autorizadas",
            "roles": "Roles",
            "estado": "Estado",
        }
        widgets = {
            "identificador_inst": forms.TextInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "nombres": forms.TextInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "apellidos": forms.TextInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "email": forms.EmailInput(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "cargo": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "delegacion": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "delegaciones_autorizadas": forms.CheckboxSelectMultiple,
            "delegaciones_autorizadas": forms.CheckboxSelectMultiple,
            "estado": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "roles": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].queryset = Cargo.objects.filter(estado="activo").order_by("nombre")
        self.fields["delegacion"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
        self.fields["delegaciones_autorizadas"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
        self.fields["delegaciones_autorizadas"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
        self.fields["roles"].queryset = Rol.objects.order_by("nombre")
        self.fields["cargo"].required = True
        self.fields["delegacion"].required = True
        self.fields["roles"].required = True

    def clean_password(self):
        password = self.cleaned_data.get("password")
        if not self.instance.pk and not password:
            raise forms.ValidationError("La contraseña es obligatoria al crear un usuario.")
        return password

    def save(self, commit=True):
        usuario = super().save(commit=False)
        password = self.cleaned_data.get("password")
        if password:
            usuario.password_hash = make_password(password)
        if commit:
            usuario.save()
            self.save_m2m()
        return usuario
