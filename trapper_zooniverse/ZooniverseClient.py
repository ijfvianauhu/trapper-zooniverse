import os
import time
import urllib.request
import tempfile
import logging
from random import random
from typing import List, Dict, Any, Tuple, TypedDict
from dataclasses import dataclass, field, asdict
from collections import defaultdict
import random
import panoptes_client as pc
from panoptes_client import SubjectSet, Subject, Project
from datetime import datetime

class MediaObservationEntry(TypedDict):
    filePath: str
    filePublic: bool
    fileName: str
    timestamp: datetime
    deploymentID: str
    fileMediatype : str
    observationTypes: List[str]

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


class ZooniverseClientComponent:
    def __init__(self, client = None):
        self.client = client

#
# SubjectSetsComponent
#

class SubjectSetsComponent(ZooniverseClientComponent):

    def get_all(self) -> List[SubjectSet]:
        """
        Retrieves all subject sets associated with the current Zooniverse project.

        Returns
        -------
        List[SubjectSet]
            A list of `SubjectSet` objects available for the connected project.

        Raises
        ------
        ConnectionError
            If the client is not connected to Zooniverse or the request fails.
        ValueError
            If the project ID is missing or invalid.

        Notes
        -----
        This method queries the Zooniverse API using the authenticated client
        and returns all subject sets linked to the project specified during initialization.
        """
        project = Project.find(self.client.project_id)
        subject_sets = SubjectSet.where(project_id=project.id)
        return list(subject_sets)

    def get_by_id(self, subject_set_id: int) -> SubjectSet:
        """
        Recupera un SubjectSet por su ID.

        Parameters
        ----------
        subject_set_id : int
            ID del SubjectSet a recuperar.

        Returns
        -------
        SubjectSet
            El SubjectSet correspondiente al ID proporcionado.

        Raises
        ------
        ValueError
            Si no se encuentra un SubjectSet con el ID dado.
        """
        subject_set = SubjectSet.find(subject_set_id)
        if not subject_set:
            raise ValueError(f"SubjectSet with ID {subject_set_id} not found.")
        return subject_set

    def exists(self, name: str) -> bool:
        """
        Comprueba si existe un SubjectSet con el nombre dado en el proyecto.

        Parameters
        ----------
        name : str
            Nombre del SubjectSet a buscar.

        Returns
        -------
        bool
            True si existe, False en caso contrario.
        """

        subject_sets = self.get_all()
        return any(ss.display_name == name for ssMediaObservationEntry in subject_sets)

    def create(self, name:str):
        """
        Crea un SubjectSet por nombre. Si existe, no lo crea.

        Args:
            name (str): Nombre del SubjectSet.
        Returns:
            pc.SubjectSet: El SubjectSet existente o recién creado.
        """

        existing_sets = [ss for ss in self.get_all() if ss.display_name == name]

        if existing_sets:
            return existing_sets[0]

        subject_set = pc.SubjectSet()
        subject_set.links.project = self.client.project_id
        subject_set.display_name = name
        subject_set.save()

        return subject_set

#
# SubjectsComponent
#

class SubjectsComponent(ZooniverseClientComponent):

    def get_by_subjectset(self, subject_set_id) -> List:
        """
        Retrieve all subjects associated with a given SubjectSet.

        Parameters
        ----------
        subject_set_id : int
            The ID of the SubjectSet to fetch subjects from.

        Returns
        -------
        List
            A list of Subject objects from the SubjectSet.
        """
        # Connect to Zooniverse

        #Panoptes.connect(username=username, password=password)

        # Find the SubjectSet
        subject_set = SubjectSet.find(subject_set_id)

        # Return the subjects as a list
        return list(subject_set.subjects)

    def create(self, path: str, subject_set, attempts=5, delay_seconds=60):
        """
        Try to upload a subject to Zooniverse with exponential backoff retries.

        Parameters
        ----------
        path : str
            Local path to the image file.
        subject_set : SubjectSet
            The Zooniverse SubjectSet to which the subject will be added.
        attempts : int, optional
            Maximum number of attempts before giving up.
        delay_seconds : int, optional
            Base delay (in seconds) between retries. Each retry doubles this delay.

        Returns
        -------
        Subject | None
            The uploaded Subject if successful, otherwise None.
        """
        for attempt in range(1, attempts + 1):
            try:
                self.client.logger.debug(f"[Attempt {attempt}/{attempts}] Uploading... {path}")
                subject = Subject()
                subject.links.project = self.client.project_id
                subject.metadata['Filename'] = path
                subject.add_location(path)
                subject.save()
                self.client.logger.debug(f"✅ Successfully uploaded {path}")
                subject_set.add(subject)
                return subject
            except Exception as e:
                self.client.logger.error(f"Error uploading path {e}")
                if attempt < attempts:
                    wait_time = delay_seconds * (2 ** (attempt - 1))
                    time.sleep(wait_time)

        return None

    def create_bulk(self, file_paths, subject_set:SubjectSet, attempts=5, delay=15, max_attempts_per_subject=5, delay_seconds_per_subject=30):
        """
        Upload multiple subjects to a Zooniverse SubjectSet with batch-level retries.
        If any uploads fail, retries only those in subsequent rounds, with increasing delay.

        Parameters
        ----------
        file_paths : list[str]
            Paths to the image files to upload.
        subject_set : SubjectSet
            The Zooniverse SubjectSet to which subjects will be added.
        max_attempts : int, optional
            Maximum number of retry rounds for failed uploads.
        initial_delay_seconds : int, optional
            Initial wait time between retry rounds (in seconds).
        delay_increment_seconds : int, optional
            Additional seconds added to the delay after each failed round.

        Returns
        -------
        dict
            {
                "subjects": List[Subject],  # Successfully uploaded subjects
                "failed": List[str]         # Files that failed after all attempts
            }
        """
        remaining_files = list(file_paths)
        all_subjects = []
        failed_files = []

        for attempt in range(1, attempts + 1):
            self.client.logger.debug(f"[Attempt {attempt}/{attempts}] Uploading subjects...")
            current_failed = []

            for path in remaining_files:

                subject = self.create(path,
                                      subject_set,
                                      max_attempts_per_subject,
                                      delay_seconds_per_subject
                )
                if subject:
                    all_subjects.append({"path": path, "subject_id": subject.id})
                else:
                    current_failed.append(path)
            if not current_failed:
                self.client.logger.debug(("All files uploaded successfully!"))
                break

            if attempt < attempts:
                self.client.logger.error(f"Error uploading subjects {e}")
                wait_time = delay * (2 ** (attempt - 1))
                time.sleep(wait_time)
                remaining_files = current_failed  # Volver a intentar sólo las fallidas
            else:
                self.client.logger.error(f"Giving up after {attempts} attempts. {len(current_failed)} files failed.")
                failed_files.extend(current_failed)

        return (all_subjects, failed_files)


#
# ZooniverseClient
#
class ZooniverseClient:
    """
    Clase para subir imágenes a Zooniverse y obtener resultados de un SubjectSet.
    """

    def __init__(self, project_id:str, username: str , password: str):
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
        self.project_id = project_id
        self.username = username
        self.password = password

        self.date_format = "%Y:%m:%d %H:%M:%S"
        self.logger = logging.getLogger(__name__)

        self.subjectsets: SubjectSetsComponent = SubjectSetsComponent(self)
        self.subjects: SubjectsComponent = SubjectsComponent(self)

    @classmethod
    def from_environment(cls, temp_folder: str = "temp_images") -> "ZooniverseClient":
        """
        Creates an instance using environment variables.

        This method retrieves the following environment variables:
        - ``ZOONIVERSE_PROJECT_ID``
        - ``ZOONIVERSE_USERNAME``
        - ``ZOONIVERSE_PASSWORD``

        Parameters
        ----------
        temp_folder : str, optional
            Name of the temporary folder used to store images, by default "temp_images".

        Returns
        -------
        cls
            An instance of the class initialized with the credentials and project ID.

        Raises
        ------
        ValueError
            If any of the required environment variables are not set.
        """
        project_id = os.getenv("ZOONIVERSE_PROJECT_ID")
        username = os.getenv("ZOONIVERSE_USERNAME")
        password = os.getenv("ZOONIVERSE_PASSWORD")

        if not all([project_id, username, password]):
            raise ValueError(
                "Environment variables ZOONIVERSE_PROJECT_ID, ZOONIVERSE_USERNAME and ZOONIVERSE_PASSWORD must be set."
            )
        return cls(project_id, username, password, temp_folder)


    def connect(self):
        """Conecta a Zooniverse usando las credenciales proporcionadas."""
        pc.Panoptes.connect(username=self.username, password=self.password)

    def upload_collection(
            self,
            subjectset_name: str,
            collection_info: Dict[str, 'MediaObservationEntry'],
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
        self.logger.debug("Preparando las secuencias")
        sequences = self._generate_zoo_images_from_media_map(collection_info, max_interval, n_images_seq)

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

            # Subir a Zooniverse
            file_paths = [
                os.path.join(temp_dir, f)
                for f in os.listdir(temp_dir)
                if os.path.isfile(os.path.join(temp_dir, f))
            ]

            self.connect()
            self.logger.debug(f"Creando SubjectSet {subjectset_name} en Zooniverse")
            subjectset = self.subjectsets.create(subjectset_name)

            ok, fail = self.subjects.create_bulk(
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