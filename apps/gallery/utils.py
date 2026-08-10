import unicodedata


def normalizar(texto):
    """
    Minúsculas sin tildes ni diacríticos.

    Se usa para el campo denormalizado de búsqueda: así «inauguración»
    encuentra resultados escritos como «inauguracion» y viceversa, sin
    depender de extensiones de Postgres.
    """
    if not texto:
        return ""
    descompuesto = unicodedata.normalize("NFKD", str(texto))
    sin_tildes = "".join(c for c in descompuesto if not unicodedata.combining(c))
    return " ".join(sin_tildes.lower().split())
