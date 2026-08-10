from datetime import date

from django import forms
from django.core.exceptions import ValidationError

from apps.core import imagenes
from apps.gallery.models import ANIO_MINIMO, Categoria, Fotografia


class FormularioFotografia(forms.ModelForm):
    """
    Alta y edición de fotografías.

    ``archivo`` no es un campo del modelo: la imagen se procesa (reorientar,
    redimensionar, comprimir, miniatura) y se guarda como binario en Postgres.
    """

    archivo = forms.ImageField(
        label="Archivo de imagen",
        required=False,
        widget=forms.ClearableFileInput(attrs={"class": "campo-archivo", "accept": "image/jpeg,image/png,image/webp"}),
        help_text="JPG, PNG o WEBP. Al editar, déjalo vacío para conservar la imagen actual.",
    )

    class Meta:
        model = Fotografia
        fields = ["titulo", "descripcion", "anio", "categoria", "publicada", "destacada"]
        widgets = {
            "titulo": forms.TextInput(attrs={"class": "campo", "placeholder": "Ej. Inauguración de la sede Palmira"}),
            "descripcion": forms.Textarea(
                attrs={"class": "campo", "rows": 5, "placeholder": "Contexto, personas, lugar del registro…"}
            ),
            "anio": forms.NumberInput(
                attrs={"class": "campo", "min": ANIO_MINIMO, "max": date.today().year + 1, "placeholder": "2024"}
            ),
            "categoria": forms.Select(attrs={"class": "campo"}),
            "publicada": forms.CheckboxInput(attrs={"class": "casilla"}),
            "destacada": forms.CheckboxInput(attrs={"class": "casilla"}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["categoria"].queryset = Categoria.objects.filter(activa=True)
        self.fields["categoria"].empty_label = "Selecciona una categoría"
        # El PK es un UUID con default, así que `instance.pk` nunca es None:
        # para saber si es un alta hay que mirar el estado del modelo.
        self.es_alta = self.instance._state.adding
        if self.es_alta:
            self.fields["archivo"].required = True
        self._procesada = None

    def clean_anio(self):
        anio = self.cleaned_data["anio"]
        limite = date.today().year + 1
        if anio < ANIO_MINIMO or anio > limite:
            raise ValidationError(f"Indica un año entre {ANIO_MINIMO} y {limite}.")
        return anio

    def clean_archivo(self):
        archivo = self.cleaned_data.get("archivo")
        if not archivo:
            return archivo
        self._procesada = imagenes.procesar(archivo)  # propaga ValidationError legible
        return archivo

    def clean(self):
        datos = super().clean()
        # Red de seguridad: nunca guardar una fotografía sin binario.
        if self._procesada is None and self.es_alta:
            self.add_error("archivo", "Selecciona el archivo de imagen de la fotografía.")
        return datos

    def save(self, commit=True, usuario=None):
        foto = super().save(commit=False)
        if self._procesada is not None:
            foto.aplicar_imagen(self._procesada, getattr(self.cleaned_data.get("archivo"), "name", ""))
        if usuario is not None and foto.subida_por_id is None:
            foto.subida_por = usuario
        if commit:
            foto.save()
        return foto


class FormularioCategoria(forms.ModelForm):
    class Meta:
        model = Categoria
        fields = ["nombre", "descripcion", "color", "orden", "activa"]
        widgets = {
            "nombre": forms.TextInput(attrs={"class": "campo", "placeholder": "Ej. Evento"}),
            "descripcion": forms.TextInput(attrs={"class": "campo", "placeholder": "Descripción breve"}),
            "color": forms.TextInput(attrs={"class": "campo campo-color", "type": "color"}),
            "orden": forms.NumberInput(attrs={"class": "campo", "min": 0}),
            "activa": forms.CheckboxInput(attrs={"class": "casilla"}),
        }
