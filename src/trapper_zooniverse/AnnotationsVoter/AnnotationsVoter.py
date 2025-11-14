from typing import List, Tuple, Optional
from abc import ABC, abstractmethod
from trapper_zooniverse.Schemas import Zoo2TrapperObservation

class AnnotationsVoter(ABC):
    """
    Se encarga de procesar los exports de Zooniverse y construir
    estructuras de datos con anotaciones y resúmenes.
    """
    @staticmethod
    @abstractmethod
    def run(classifications:List[Tuple[str, dict]]) -> Optional[List[Zoo2TrapperObservation]]:
        pass