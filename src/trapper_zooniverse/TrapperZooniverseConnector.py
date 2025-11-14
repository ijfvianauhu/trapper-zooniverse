from collections import defaultdict
from datetime import datetime, time, timezone
import random
from pathlib import Path
from typing import List, Dict, Tuple, Any, Optional, Callable
import logging, os
import tempfile

from panoptes_client import Project, SubjectSet
from panoptes_client.panoptes import Panoptes
from pydantic import BaseModel, validator, HttpUrl
from trapper_client import Schemas
from trapper_client.TrapperClient import TrapperClient
from trapper_client.Schemas import TrapperMediaList, TrapperObservationList, Pagination, \
    TrapperObservationResultsTrapper, TrapperClassificationResultsList

from trapper_zooniverse.AnnotationsVoter import AnnotationsVoter
from trapper_zooniverse.AnnotationsExtractor import AnnotationsExtractor
from trapper_zooniverse.reports import Report
from trapper_zooniverse.Schemas import UploadReport, SubjectSetResults, WorkflowData, UploadAnnotationsReport, \
    Zoo2TrapperObservation, UploadMediaReport

import urllib

from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils


class MediaObservationEntry(BaseModel):
    filePath: HttpUrl
    filePublic: bool
    fileName: str
    timestamp: Optional[datetime]
    deploymentID: str
    fileMediatype : str
    observations: List[str]

    @validator("timestamp", pre=True, always=True)
    def parse_timestamp(cls, v):
        """
        Convierte cadenas vacías en None.
        Si es una cadena no vacía, intenta parsearla como datetime.
        """
        if not v:  # None, "" o valores falsy
            return None
        if isinstance(v, datetime):
            return v
        try:
            return datetime.fromisoformat(v)
        except Exception:
            # opcional: lanzar error o devolver None si no se puede parsear
            return None


class TrapperZooniverseConnector:
    """
    Clase para subir imágenes a Zooniverse y obtener resultados de un SubjectSet.
    """

    def __init__(self, zoo: ZooniverseClient, trapper: TrapperClient):
        """
        Initializes a new instance of the class with project credentials and identifier.

        Parameters
        ----------
        project_id : str
            Unique identifier of the project associated with this instance.
        username : str
            Username used for authentication.
        password : str
            Password associated with the given username.
        """
        self.zoo     = zoo
        self.trapper = trapper

        self.date_format = "%Y:%m:%d %H:%M:%S"
        self.logger = logging.getLogger(__name__)

    def upload_collection(
            self,
            subjectset_name: str,
            collection:int,
            classification_project:int,
            uploaded_file,
            n_images_seq=5,
            max_interval=120,
            attempts=5,
            delay=15,
            max_attempts_per_subject=5,
            delay_seconds_per_subject=30,
            progress_callback: Optional[Callable[[str, int], None]] = None  # <--- callback
    ) -> Report:
        report2 = Report(f"Collection {collection} from {self.trapper.base_url}", type="UploadMediaReport" )
        metadata = {}

        start_time = datetime.now().isoformat()
        self.logger.debug(f"Starting upload_collection at {start_time}")

        print(f"Getting media for {classification_project} and collection {collection}...")
        media:TrapperMediaList=self.trapper.media.get_by_collection(classification_project, collection)

        self.logger.debug(
            f"Obtained {len(media.results)} media from classification project {classification_project} and collection {collection}")

        print(f"Getting observations from classification project  {classification_project} and collection {collection}")
        observations:TrapperClassificationResultsList=(self.trapper.observations.results.get_by_collection(classification_project, collection))
        self.logger.debug(
            f"Obtained {len(observations.results)} observations from classification project  {classification_project} and collection {collection}")

        if progress_callback:
            progress_callback("get_observations", len(observations.results))

        print(f"Filtering classified observations...")

        filtered_observations = [
            obs for obs in observations.results
            if obs.observationType != "unclassified"
               and obs.classifiedBy is not None
               and obs.classificationTimestamp is not None
        ]

        if len(filtered_observations) == 0:
            self.logger.warning(f"No observations found after filtering for collection {collection} and classification project {classification_project}.")

        observations = TrapperClassificationResultsList(
            **{
                "results": filtered_observations,
                "pagination": Pagination(
                    page=1,
                    page_size=len(filtered_observations),
                    pages=1,
                    count=len(filtered_observations)
                )
            }
        )

        self.logger.debug(
            f"Obtained {len(observations.results)} observations after filtering from classification project  {classification_project} and collection {collection}")

        print(f"Geering utl for medias classified...")

        media_map=self._merge_media_and_observations(media,observations)

        self.logger.debug(
            f"Obtained {len(media_map.keys())} observations_media from classification project  {classification_project} and collection {collection}")

        if len(media_map.keys()) == 0:
            self.logger.debug(f"No valid observations found for collection {collection} and classification project {classification_project}.")

        self.logger.debug("Preparando las secuencias")
        print(f"PReparing secuencias..")

        sequences = self._generate_zoo_images_from_media_map(media_map, max_interval, n_images_seq)

        print(f"Downloading images..")

        with tempfile.TemporaryDirectory() as temp_dir:
            for idx, seq in enumerate(sequences):
                is_first = idx == 0
                is_last = idx == len(sequences) - 1

                for media in seq:
                    # Excluir si es privada
                    if not media.get("filePublic", False):
                        self.logger.warning(f"Excluyendo imagen privada {media['mediaID']} {media['filePath']}")
                        report2.add_error(f"{media['mediaID']}@media", "select","skipped_private")
                        continue

                    # Excluir si no es animal (solo para secuencias intermedias)
                    if not is_first and not is_last:
                        obs_types = media.get("observationTypes", [])
                        if any(o.lower() != "animal" for o in obs_types):
                            self.logger.warning(
                                f"Excluyendo {media['mediaID']} {media['filePath']} con tipos {media['observationTypes']}")
                            report2.add_error(f"{media['mediaID']}@media", "select","skipped_human")
                            continue

                    name = self._get_zoo_filename(media)
                    local_path = os.path.join(temp_dir, name)

                    self.logger.debug(
                        f"Descargando {media['mediaID']} ({media['filePath']}) a {local_path}")

                    try:
                        self._download_image(str(media['filePath']), local_path, attempts=5, delay_seconds=60)
                        origin = f"{self.trapper.base_url}:media:{media['mediaID']}"
                        metadata[name] = {"origin":origin}
                        report2.add_success(f"{media['mediaID']}@media", "download",**{"path":local_path})
                        import time
                        import random
                        time.sleep(random.uniform(1, 4))
                    except Exception as e:
                        self.logger.error(f"Failed to download {media['mediaID']}: {e}")
                        report2.add_error(f"{media['mediaID']}@media",
                                          "download",
                                          str(e),
                                          **{"path":str(media['filePath'])})
                    finally:
                        if progress_callback:
                            progress_callback("download", 1)  # incrementa 1 unidad
            # Subir a Zooniverse
            file_paths = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f))
            ]
            self.logger.debug(f"Creando SubjectSet {subjectset_name} en Zooniverse")
            subjectset = self.zoo.subjectsets.create(subjectset_name)

            ok, fail = self.zoo.subjects.create_bulk(
                file_paths,
                subjectset,
                metadata,
                attempts,
                delay,
                max_attempts_per_subject,
                delay_seconds_per_subject,
            )

            for success in ok:
                import re
                match=re.search(r"/(\d+)_.*$",success["path"])
                media_id = match.group(1)
                report2.add_success(f"{media_id}@media", "upload",
                                    **{"subject_id": success["subject_id"], "path": success["path"]})

            for failure in fail:
                import re
                match = re.search(r"/(\d+)_.*$", success["path"])
                media_id = match.group(1)
                report2.add_error(f"{media_id}@media", "upload","failed",
                                  **{"path": failure})

        report2.finish()

        return report2

    def upload_annotations(
            self,
            subjectset_id: int,
            wf_id: int,
            collection_id: int,
            cp_id: int,
            output_dir: Path = None,
            observation_map: Path = None,
            species_map: Path = None,
    ):
        report = UploadAnnotationsReport(str(subjectset_id))

        self.zoo.connect()

        annotations: SubjectSetResults = self.zoo.annotations.get_by_subjectset(subjectset_id)

        self.logger.debug(f"Obtained {len(annotations.workflows)} workflows linked to subjectset {subjectset_id}")

        wf = self.zoo.workflows.get_by_id(wf_id)
        wf_key = f"{wf.id}:{wf.display_name}:{wf.version}"

        if wf_key not in annotations.workflows:
            raise ValueError(f"Workflow key {wf_key} not found in annotations")

        annotations: WorkflowData = annotations.workflows[wf_key]

        self.logger.debug(
            f"Obtained {len(annotations.data)} annotations for subjectset {subjectset_id} and workflow {wf_id}"
        )

        observations: Schemas.TrapperObservationList = self.trapper.observations.get_by_classification_project_and_collection(
            cp_id, collection_id
        )

        self.logger.debug(
            f"Obtained {len(observations.results)} observations for collection {collection_id} and research project {cp_id}")

        (extrator, voter) = self._get_extrator_vote(wf.id)

        #indices = random.sample(range(len(observations.results)), len(observations.results))

        flat_results : List[TrapperObservationResultsTrapper]= []

        for key, value in annotations.data.items():
            try:
                self.logger.debug(f"Procesando observaciones para el subject-media {key}")
                subject_id, media_id = key.split(":")

                # Fake code begins
                #n = random.randint(0, min(3, len(indices)))
                #removed = indices[:n]
                #indices = indices[n:]
                #all_media_observations = [observations.results[i] for i in removed]
                ### Fake code end

                all_media_observations: List[TrapperObservationResultsTrapper] = [o for o in observations.results if str(o.mediaID) == media_id]

                opinions = extrator.run(value)

                if len(all_media_observations) == 0:
                    self.logger.debug(f"No encontrado {media_id} en observaciones")
                    report.add_error(
                        f"subject:{subject_id}",
                        f"No observations found for resource {media_id} in Trapper classification project {cp_id}"
                    )
                else:
                    # Zooniverse decision
                    decision : List[Zoo2TrapperObservation] = voter.run(opinions)

                    if not decision:
                        report.add_error(f"subject:{subject_id}",
                                         f"No annotations found for resource {media_id} in subject {subject_id}")
                        self.logger.debug(f"No hay anotaciones para media {media_id} y subject_id {subject_id}")
                        continue

                    for ob in all_media_observations:
                        for d in decision:
                            new_obs: TrapperObservationResultsTrapper = ob.copy(update={
                                **d.model_dump(),
                                "bboxes": None,
                                "classificationTimestamp": datetime.now(timezone.utc),
                                "classifiedBy": self.trapper.user_name,
                                "classificationMethod": "human",
                                "observationComments": f"Automatically classified by Zooniverse in workflow {wf_key} for subject {subject_id}"
                            })
                            report.add_success(
                                f"subject:{subject_id}",
                                f"Added an observation for resource {media_id} with {decision[0].scientificName}"
                            )

                            flat_results.append(new_obs)

                    """if len(decision) == 1:
                        for ob in all_media_observations:
                            new_obs : TrapperObservation = ob.copy(update={
                                **decision[0].model_dump(),
                                "classificationTimestamp": datetime.now(timezone.utc),
                                "classifiedBy": self.trapper.user_name,
                                "classificationMethod": "human",
                                "observationComments": f"Automatically classified by Zooniverse in workflow {wf_key} for subject {subject_id}"
                            })
                            report.add_success(
                                f"subject:{subject_id}",
                                f"Added an observation for resource {media_id} with {decision[0].scientificName}"
                            )

                            flat_results.append(new_obs)
                    else:
                        report.add_error(f"subject:{subject_id}",
                                         f"Subject contains more than one annotation ({len(decision)})")
                        self.logger.debug(
                            f"Votación no concluyente para media {media_id} y subject_id {subject_id}: {decision}")"""
            except Exception as e:
                self.logger.error("unknown", f"Error processing subject-media {key}: {e}")

        self.logger.debug(
            f"Generadas {len(flat_results)} observaciones para importar en Trapper por subject: "
        )

        # Construir TrapperObservationList aplanado para CSV
        res = TrapperObservationList(**
            {
                "results":flat_results,
                "pagination":{
                    "page": 1,
                    "page_size": len(flat_results),
                    "pages": 1,
                    "count": len(flat_results)
                }
            }
        )

        # Guardar CSV si se indicó output_dir
        if output_dir:
            self.logger.debug(f"Saving observations to CSV in {output_dir}")
            self._trapper_observations_to_csv(res.results, Path(output_dir))

        return report

        #TODO subir usando el browser

    def _get_zoo_filename(self, media):
        extension = media['fileMediatype'].split("/")[1]
        return f"{media['mediaID']}_x_{media['deploymentID']}_x_{media['fileName']}.{extension}"

    def _get_extrator_vote(self, workflow_id) -> Tuple[AnnotationsExtractor, AnnotationsVoter]:
        import importlib

        extractor_class_name = f"Workflow{workflow_id}AnnotationExtractor"
        voter_class_name = f"Workflow{workflow_id}AnnotationsVoter"

        extractor_module = importlib.import_module(f"trapper_zooniverse.AnnotationsExtractor.{extractor_class_name}")
        voter_module = importlib.import_module(f"trapper_zooniverse.AnnotationsVoter.{voter_class_name}")

        ExtractorClass = getattr(extractor_module, extractor_class_name)
        VoterClass = getattr(voter_module, voter_class_name)

        return ExtractorClass, VoterClass

    def _download_image(self, url: str, dest_path: str, attempts=5, delay_seconds=60) -> bool:
        """Descarga una imagen desde una URL con reintentos."""
        for attempt in range(attempts):
            try:
                urllib.request.urlretrieve(url, dest_path)
                return True
            except Exception as e:
                self.logger.error(f"Error downloading {url} (attempt {attempt + 1}/{attempts}): {e}")
                if attempt < attempts - 1:
                    time.sleep(delay_seconds)
        return False

    def _merge_media_and_observations( self,
            media :TrapperMediaList,
            observations: TrapperObservationList
    ) -> Dict[str, MediaObservationEntry]:
        """
        Merge media and observations into a single dictionary keyed by mediaID.

        Parameters
        ----------
        results : tuple
            Tuple containing (media, observations) results, usually from run_tasks_with_progress.
        cp_pk : int
            Classification project ID (for logging purposes).
        collection : int
            Collection ID (for logging purposes).

        Returns
        -------
        Dict[str, MediaObservationEntry]
            Dictionary mapping mediaID to its media data and associated observation types.
        """

        media_map: Dict[str, MediaObservationEntry] = {}
        media_ids = { m.mediaID for m in getattr(media, "results", []) }

        for obs in getattr(observations, "results", []):
            media_id = str(obs.mediaID)

            if obs.mediaID in media_ids:
                obs_type = getattr(obs, "observationType", None)

                if obs.mediaID not in media_map:
                    media_info = [m for m in media.results if m.mediaID ==  obs.mediaID]

                    media_map[obs.mediaID] = MediaObservationEntry(**{
                        "filePath": media_info[0].filePath,
                        "filePublic": media_info[0].filePublic,
                        "fileName": media_info[0].fileName,
                        "deploymentID": media_info[0].deploymentID,
                        "fileMediatype": media_info[0].fileMediatype,
                        "timestamp": media_info[0].timestamp,
                        "observations": []
                    }
                    )

                if obs_type:

                    if isinstance(obs_type, list):
                        media_map[obs.mediaID].observations.extend(obs_type)
                    else:
                        media_map[obs.mediaID].observations.append(obs_type)
            else:
                self.logger.warning(f"No  encontré información sobre el media {media_id} asociado a la observacion")
        return media_map

    def _show_sequences_as_json(self,sequences):
        """
        Muestra una lista de secuencias (por ejemplo, listas de MediaObservationEntry)
        formateadas en JSON con indentación jerárquica.
        """

        # Si los objetos tienen campos datetime, los convertimos a string
        def default_serializer(obj):
            if hasattr(obj, "isoformat"):
                return obj.isoformat()
            return str(obj)

        import json
        return (json.dumps(sequences, indent=4, default=default_serializer))

    def _generate_zoo_images_from_media_map(self, media_map: Dict[str, MediaObservationEntry], max_interval, n_images_seq) -> List[Dict[str, Any]]:
        """Genera las imágenes que se subirán a Zooniverse a partir de un media_map."""
        #print(media_map)
        #self.logger.debug(("Convirtiendo timestamps"))
        rows = self._convert_timestamps_from_media_map(media_map)
        self.logger.debug(("Agrupando media por deployment"))
        grouped = self._group_by_deployment(rows)

        sampled_sequences = []

        for group in grouped.values():
            ordered = sorted(group, key=lambda x: x['timestamp'])

            # Generamos las secuencias, una secuencia es un conjunto de imágenes tomadas
            # en instantes de tiempo consecutivos, separados por menos de max_interval segundos.

            sequences = []
            current_seq = [ordered[0]]

            for prev, curr in zip(ordered, ordered[1:]):
                delta = (curr['timestamp'] - prev['timestamp']).total_seconds()
                if delta <= max_interval:
                    current_seq.append(curr)
                else:
                    # Cierra la secuencia actual y empieza una nueva
                    sequences.append(current_seq)
                    current_seq = [curr]

            sequences.append(current_seq)
            #self.logger.debug(f"Secuencias obtenidas {len(sequences)}: {self._show_sequences_as_json(sequences)}")
            self.logger.debug(f"Secuencias obtenidas {len(sequences)}")
            self.logger.debug(f"Muestreando secuencias...")

            # Muestreamos cada scuencias
            for seq in sequences:
                self.logger.debug(f"Muestreando secuencias con {len(seq)} imagenes...")
                sampled = self._sample_sequence(seq, n_images_seq)
                self.logger.debug(f"Obtenido muestreo de {len(sampled)} imagenes...")
                sampled_sequences.append(sampled)

            #self.logger.debug(f"Secuencias muestreadas {self._show_sequences_as_json(sampled_sequences)}")

        return sampled_sequences

    def _sample_sequence(self, rows: List[Dict], n_images_seq) -> List[Dict]:
        """Selecciona un subconjunto de imágenes distribuidas uniformemente."""
        if len(rows) <= n_images_seq:
            return rows
        step = (len(rows) - 1) / (n_images_seq - 1) if n_images_seq > 1 else 0
        indices = [round(i * step) for i in range(n_images_seq)]
        return [rows[i] for i in indices]

    def _count_until_threshold(self, differences: List[float], max_interval) -> Tuple[int, List[float]]:
        """Cuenta cuántas imágenes están dentro del umbral de tiempo."""
        for i, val in enumerate(differences):
            if val > max_interval:
                return i, differences[i:]
        return len(differences), []

    def _convert_timestamps_from_media_map(self, media_map: Dict[str, MediaObservationEntry]) -> List[Dict]:
        """Convierte timestamps ISO8601 a objetos datetime (in place)."""
        rows = []
        for mid, data in media_map.items():
            try:
                data.timestamp= datetime.fromisoformat(data.timestamp)
            except Exception as e:
                pass  # si no se puede convertir, se deja como está

            rows.append({**data.model_dump(), "mediaID": mid})
        return rows

    def _group_by_deployment(self, rows: List[Dict]) -> Dict[str, List[Dict]]:
        """Agrupa las imágenes por deploymentID."""
        groups = defaultdict(list)
        for row in rows:
            deployment = row.get('deploymentID', 'unknown')
            groups[deployment].append(row)
        return groups

    def _trapper_observations_to_csv(self, observations: List[TrapperObservationResultsTrapper], path: Path):
        import csv

        def format_datetime(value):
            if isinstance(value, datetime):
                return value.strftime("%Y-%m-%dT%H:%M:%S%z")
            return value

        # Convertir modelos a dicts
        data = [obs.model_dump(by_alias=True) for obs in observations]

        # Formatear las fechas
        for row in data:
            for key, value in row.items():
                row[key] = format_datetime(value)

        # Obtener las cabeceras del primer elemento
        fieldnames = data[0].keys() if data else []

        with path.open("w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(data)

    @staticmethod
    def _load_uploaded_files_list(path: str) -> list[str]:
        """
        Lee un archivo de texto que contiene rutas de archivos (uno por línea)
        y devuelve una lista con esos paths.
        Se usa para mantener registro de las imágenes ya subidas o con errores.
        """
        if not os.path.exists(path):
            return []
        with open(path, 'r', encoding='utf-8') as f:
            return [line.strip() for line in f if line.strip()]