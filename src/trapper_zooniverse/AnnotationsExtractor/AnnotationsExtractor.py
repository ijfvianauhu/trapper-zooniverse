from typing import List, Tuple

from trapper_zooniverse.Schemas import ClassificationInfo

class AnnotationsExtractor:
    """
    Se encarga de procesar los exports de Zooniverse y construir
    estructuras de datos con anotaciones y resúmenes.
    """

    @staticmethod
    def run(classifications:List[ClassificationInfo]) -> List[Tuple[str, dict]]:
        pass
