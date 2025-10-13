from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, time
import random
from typing import TypedDict, List, Dict, Tuple, Any
import logging, os
import tempfile
from trapper_client.TrapperClient import TrapperClient
from trapper_zooniverse.ZooniverseClient import ZooniverseClient, UploadReport
import urllib

class MediaObservationEntry(TypedDict):
    filePath: str
    filePublic: bool
    fileName: str
    timestamp: datetime
    deploymentID: str
    fileMediatype : str
    observations: List[str]

@dataclass
class UploadReport:
    start_time: str
    end_time: str
    subjectset_name: str
    uploaded_images: List[str] = field(default_factory=list)
    failed_uploads: List[str] = field(default_factory=list)
    skipped_human: List[Dict] = field(default_factory=list)
    skipped_private: List[Dict] = field(default_factory=list)
    download_images: List[str] = field(default_factory=list)
    download_failed: List[Dict] = field(default_factory=list)

    def summary(self) -> str:
        """Devuelve un resumen legible del informe."""
        return (
            f"Upload report for subject set '{self.subjectset_name}'\n"
            f"Started at: {self.start_time}\n"
            f"Ended at:   {self.end_time}\n"
            f"Uploaded images: {len(self.uploaded_images)}\n"
            f"Failed uploads:  {len(self.failed_uploads)}\n"
            f"Skipped (human): {len(self.skipped_human)}\n"
            f"Skipped (private): {len(self.skipped_private)}\n"
            f"Downloaded: {len(self.download_images)}\n"
            f"Download failed: {len(self.download_failed)}"
        )


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
    ) -> UploadReport:

        start_time = datetime.now().isoformat()
        self.logger.debug(f"Starting upload_collection at {start_time}")

        media=self.trapper.media.get_by_classification_project_and_collection(classification_project, collection),
        observations=self.trapper.observations.get_by_classification_project_and_collection(classification_project, collection)

        media_map=self._merge_media_and_observations(media,observations)

        self.logger.debug("Preparando las secuencias")
        sequences = self._generate_zoo_images_from_media_map(media_map, max_interval, n_images_seq)

        uploaded_images = []
        failed_uploads = []
        skipped_human = []
        skipped_private = []
        download_images = []
        download_failed = []

        with tempfile.TemporaryDirectory() as temp_dir:
            for idx, seq in enumerate(sequences):
                is_first = idx == 0
                is_last = idx == len(sequences) - 1

                for media in seq:
                    # Excluir si es privada
                    if not media.get("filePublic", False):
                        self.logger.warning(f"Excluyendo imagen privada {media['mediaID']} {media['filePath']}")
                        skipped_private.append(media)
                        continue

                    # Excluir si no es animal (solo para secuencias intermedias)
                    if not is_first and not is_last:
                        obs_types = media.get("observationTypes", [])
                        if any(o.lower() != "animal" for o in obs_types):
                            self.logger.warning(
                                f"Excluyendo {media['mediaID']} {media['filePath']} con tipos {media['observationTypes']}")
                            skipped_human.append(media)
                            continue

                    extension = media['fileMediatype'].split("/")[1]
                    name = f"{media['mediaID']}_x_{media['deploymentID']}_x_{media['fileName']}.{extension}"
                    local_path = os.path.join(temp_dir, name)

                    self.logger.debug(
                        f"Descargando {media['mediaID']} ({media['filePath']}) a {local_path}")

                    try:
                        self._download_image(str(media['filePath']), local_path, attempts=5, delay_seconds=60)
                        download_images.append(local_path)
                        time.sleep(random.uniform(1, 4))
                    except Exception as e:
                        self.logger.error(f"Failed to download {media['mediaID']}: {e}")
                        download_failed.append(media)

            # Subir a ZooniverseTyptempfilee
            file_paths = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f))
            ]

            self.zoo.connect()
            self.logger.debug(f"Creando SubjectSet {subjectset_name} en Zooniverse")
            subjectset = self.zoo.subjectsets.create(subjectset_name)

            ok, fail = self.zoo.subjects.create_bulk(
                file_paths,
                subjectset,
                attempts,
                delay,
                max_attempts_per_subject,
                delay_seconds_per_subject,
            )

            uploaded_images.extend(ok)
            failed_uploads.extend(fail)

        end_time = datetime.now().isoformat()

        report = UploadReport(
            start_time=start_time,
            end_time=end_time,
            subjectset_name=subjectset_name,
            uploaded_images=uploaded_images,
            failed_uploads=failed_uploads,
            skipped_human=skipped_human,
            skipped_private=skipped_private,
            download_images=download_images,
            download_failed=download_failed,
        )

        self.logger.info(report.summary())

        return report

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
            media,
            observations
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

        # Seleccionar campos relevantes de media
        for m in getattr(media, "results", []):
            media_map[str(m.mediaID)] = {
                "filePath": str(getattr(m, "filePath", "")),
                "filePublic": getattr(m, "filePublic", False),
                "fileName": getattr(m, "fileName", ""),
                "deploymentID": getattr(m, "deploymentID", ""),
                "fileMediatype": getattr(m, "fileMediatype", ""),
                "timestamp": getattr(m, "timestamp", ""),
                "observationTypes": []
            }

        # Añadir tipos de observación a cada media
        for obs in getattr(observations, "results", []):
            media_id = str(obs.mediaID)

            if media_id not in media_map:
                raise Exception(f"{media_id} has observations but no media!")

            obs_type = getattr(obs, "observationType", None)
            if obs_type:
                if isinstance(obs_type, list):
                    media_map[media_id]["observationTypes"].extend(obs_type)
                else:
                    media_map[media_id]["observationTypes"].append(obs_type)

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
        self.logger.debug(("Convirtiendo timestamps"))
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

            self.logger.debug(f"Secuencias muestreadas {self._show_sequences_as_json(sampled_sequences)}")

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
            if 'timestamp' in data and isinstance(data['timestamp'], str):
                try:
                    data['timestamp'] = datetime.fromisoformat(data['timestamp'])
                except ValueError:
                    pass  # si no se puede convertir, se deja como está
            rows.append({**data, "mediaID": mid})
        return rows

    def _group_by_deployment(self, rows: List[Dict]) -> Dict[str, List[Dict]]:
        """Agrupa las imágenes por deploymentID."""
        groups = defaultdict(list)
        for row in rows:
            deployment = row.get('deploymentID', 'unknown')
            groups[deployment].append(row)
        return groups

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