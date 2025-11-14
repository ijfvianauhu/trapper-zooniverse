from typing import List, Tuple

from trapper_zooniverse.Schemas import ClassificationInfo
from trapper_zooniverse.AnnotationsExtractor.AnnotationsExtractor import AnnotationsExtractor

class Workflow17553AnnotationExtractor(AnnotationsExtractor):
    """
    Extrae las anotaciones específicas del workflow 17553 (IberianCameraTrapR1_1_2_3).
    """

    """Mapeo entre las posibles respuestas que se den en zoo y las especies científicas que usa Trapper
    y el tipo de observacion ["human", "vehicle", "black", "unclassified", "unknown"]
    ."""

    zoo_to_trapper = {
        "CERVIDREDORFALLOWDEER": "unclassified", #??
        "COMMONGENET": "Genetta genetta",
        "COW": "Bos taurus",
        "EGYPTIANMONGOOSE": "Herpestes ichneumon",
        "EUROPEANBADGER": "Meles meles",
        "EUROPEANRABBIT": "Oryctolagus cuniculus",
        "FALLOWDEER": "Dama dama",
        "HORSE": "Equus (Equus) caballus",
        "HUMANORVEHICLE": "human", # ??
        "IBERIANHARE": "Lepus granatensis",
        "IBERIANLYNX": "Lynx pardinus",
        "LEPORIDRABBITORHARE": "unclassified", #¿¿
        "NOANIMAL": "human", # ??
        "OTHERSPECIES": "unknown", ##??
        "REDDEER": "Cervus elaphus hispanicus",
        "REDFOX": "Vulpes vulpes",
        "UNRECOGNIZABLE": "unknown", # ??
        "WILDBOAR": "Sus scrofa",
    }

    @staticmethod
    def run(classifications:List[ClassificationInfo]) -> List[Tuple[str, dict]]:
        choices = []

        for c in classifications:  # cada ClassificationInfo
            for ann in c.annotations:
                for v in ann.get("value", []):
                    choice = v.get("choice")
                    choice = Workflow17553AnnotationExtractor.zoo_to_trapper.get(choice, None)
                    answers = v.get("answers")
                    if choice:
                        choices.append((choice,answers,))

        return choices