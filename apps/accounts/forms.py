from django import forms
from django.contrib.auth import get_user_model

Usuario = get_user_model()


class FormularioEnlace(forms.Form):
    """Formulario público: solo pide el correo institucional."""

    correo = forms.EmailField(
        label="Correo electrónico",
        max_length=254,
        widget=forms.EmailInput(
            attrs={
                "class": "campo",
                "placeholder": "nombre@ccpalmira.org.co",
                "autocomplete": "email",
                "autofocus": "autofocus",
                "inputmode": "email",
            }
        ),
    )

    def clean_correo(self):
        return self.cleaned_data["correo"].strip().lower()


class FormularioClave(forms.Form):
    """Ingreso con contraseña, reservado al superadministrador."""

    correo = forms.EmailField(
        label="Correo electrónico",
        widget=forms.EmailInput(attrs={"class": "campo", "autocomplete": "email", "autofocus": "autofocus"}),
    )
    password = forms.CharField(
        label="Contraseña",
        widget=forms.PasswordInput(attrs={"class": "campo", "autocomplete": "current-password"}),
    )

    def clean_correo(self):
        return self.cleaned_data["correo"].strip().lower()


class FormularioUsuario(forms.ModelForm):
    """Alta y edición de personas autorizadas desde el panel."""

    class Meta:
        model = Usuario
        fields = ["correo", "nombre", "cargo", "rol", "is_active", "notas"]
        labels = {
            "is_active": "Acceso habilitado",
            "notas": "Notas internas",
        }
        help_texts = {
            "rol": "El superadministrador gestiona fotografías y usuarios; el usuario de consulta solo ve la galería.",
            "notas": "Visible únicamente para superadministradores.",
        }
        widgets = {
            "correo": forms.EmailInput(attrs={"class": "campo", "placeholder": "nombre@ccpalmira.org.co"}),
            "nombre": forms.TextInput(attrs={"class": "campo", "placeholder": "Nombre y apellidos"}),
            "cargo": forms.TextInput(attrs={"class": "campo", "placeholder": "Ej. Comunicaciones"}),
            "rol": forms.Select(attrs={"class": "campo"}),
            "notas": forms.Textarea(attrs={"class": "campo", "rows": 3}),
            "is_active": forms.CheckboxInput(attrs={"class": "casilla"}),
        }

    def clean_correo(self):
        correo = self.cleaned_data["correo"].strip().lower()
        existentes = Usuario.objects.filter(correo=correo)
        if self.instance.pk:
            existentes = existentes.exclude(pk=self.instance.pk)
        if existentes.exists():
            raise forms.ValidationError("Ya existe un usuario registrado con este correo.")
        return correo
