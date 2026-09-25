from django import forms
from django.contrib.auth.hashers import make_password

from .models import Cargo, Delegacion, Rol, Usuario


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
            "estado": forms.Select(attrs={"class": "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm"}),
            "roles": forms.CheckboxSelectMultiple,
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["cargo"].queryset = Cargo.objects.filter(estado="activo").order_by("nombre")
        self.fields["delegacion"].queryset = Delegacion.objects.filter(estado="activa").order_by("nombre")
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
