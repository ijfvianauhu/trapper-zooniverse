from typing import List
from collections import Counter
from typing import List, Tuple, Optional

from trapper_zooniverse.AnnotationsVoter.AnnotationsVoter import AnnotationsVoter
from trapper_zooniverse.Schemas import Zoo2TrapperObservation


class Workflow17553AnnotationsVoter(AnnotationsVoter):

    observationTypeMap = {
        "UNRECOGNIZABLE": "black",
        "NOANIMAL": "human",
        "HUMAN": "human",
    }

    """
    Extrae las anotaciones específicas del workflow 17553 (IberianCameraTrapR1_1_2_3).
    """
    @staticmethod
    def run(observations: List[Tuple[str, dict]]) -> Optional[List[Zoo2TrapperObservation]]:

        if not observations:
            return None

        species_counts = Counter(name for name, _ in observations)
        most_common_species, _ = species_counts.most_common(1)[0]
        filtered = [attrs for name, attrs in observations if name == most_common_species]

        howmany_values = [attrs.get("HOWMANY") for attrs in filtered if "HOWMANY" in attrs]
        observationType = most_common_species if most_common_species in ["human", "vehicle", "black", "unclassified", "unknown"] else "animal"

        if observationType == "human":
            most_common_species="Homo sapiens"
        elif observationType == "animal":
            most_common_species=most_common_species
        else:
            most_common_species=None

        count_majority = None

        if howmany_values:
            # Contar los valores HOWMANY
            count_majority = Counter(howmany_values).most_common(1)[0][0]
            # Convertir a entero si es numérico
            if count_majority.isdigit():
                count_majority = int(count_majority)

        # TODO: mapeos de observationtyoe y scientificName
        return [Zoo2TrapperObservation(**{
            "observationType": observationType,
            "scientificName": most_common_species,
            "count": int(count_majority) if isinstance(count_majority, (int, str)) and str(count_majority).isdigit() else None,
        })]