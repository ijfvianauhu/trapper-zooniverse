import os
import time
import logging
from typing import List, Dict, Any, Tuple, TypedDict, Counter, Optional
from dataclasses import dataclass, field, asdict
import json
import panoptes_client as pc
from panoptes_client import SubjectSet, Subject, Project
from pydantic import BaseModel

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
        return any(ss.display_name == name for ss in subject_sets)

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

    def with_exports(self) -> List:
        return self.with_results()

    def with_results(self) -> List:
        """
        Devuelve los subjetsts que tienen resultados.

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
        selected = []
        for ss in subject_sets:
            # Check if classifications export exists
            try:
                export = ss.get_export("classifications", wait=False)  # don't wait for generation
                selected.append(ss)
            except Exception as e:
                pass

        return selected
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
        file_paths : list[str]from datetime import datetime

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
                self.client.logger.error(f"Error uploading subjects")
                wait_time = delay * (2 ** (attempt - 1))
                time.sleep(wait_time)
                remaining_files = current_failed  # Volver a intentar sólo las fallidas
            else:
                self.client.logger.error(f"Giving up after {attempts} attempts. {len(current_failed)} files failed.")
                failed_files.extend(current_failed)

        return (all_subjects, failed_files)

#
# AnnotationsComponent
#

class SubjectResult(BaseModel):
    subject_id: int
    filename: str
    retired: bool
    annotations: List[dict]
    most_common_annotation: Optional[dict] = None
    votes: int = 0

class SubjectSetResults(BaseModel):
    subjects: List[SubjectResult]
    total_subjects: int
    retired_subjects: int

class AnnotationsComponent(ZooniverseClientComponent):

    def get_all(self):
        project = Project.find(self.client.project_id)
        subject_sets = SubjectSet.where(project_id=project.id)
        anotations = []

        for subject_set in subject_sets:
            try:
                export = subject_set.get_export("classifications", wait=False)  # don't wait for generation
                if export:
                    self.client.logger.debug(f"SubjectSet {subject_set.display_name} has classifications export.")
                    anotations.append((subject_set.id, export))
                else:
                    self.client.logger.debug(f"SubjectSet {subject_set.display_name} has no classifications export.")
            except Exception as e:
                self.client.logger.debug(f"SubjectSet {subject_set.display_name} has no classifications export.")

        return anotations


    def get_by_subjectset(self, subjectset_id: int, votes: bool=True) -> SubjectSetResults:
        """
        Fetches the results of all subjects in a SubjectSet as Pydantic models.

        :param subject_set_id: Zooniverse SubjectSet ID
        :param votes: If True, calculate the most , wait_timeout=600common annotation per subject
        :return: SubjectSetResults
        """
        subject_set = SubjectSet.find(subjectset_id)

        # Wait until export is ready
        # export = subject_set.get_export('classifications', wait=True, wait_timeout=600)

        export = subject_set.get_export('classifications', wait=False)
        exit(1)

        subjects_dict: Dict[int, SubjectResult] = {}
        total = 0
        retired_count = 0

        for row in export.csv_dictreader():
            try:
                subject_id = int(row['subject_ids'].strip().split(',')[0])
                annotations = json.loads(row['annotations'])
                subject_data = json.loads(row['subject_data'])
                metadata = subject_data.get(str(subject_id), {})
                filename = metadata.get('Filename', 'unknown')
                retired = bool(metadata.get('retired', False))

                if subject_id not in subjects_dict:
                    subjects_dict[subject_id] = SubjectResult(
                        subject_id=subject_id,
                        filename=filename,
                        retired=retired,
                        annotations=[]
                    )
                    total += 1
                    if retired:
                        retired_count += 1

                subjects_dict[subject_id].annotations.append(annotations)

            except Exception as e:
                self.client.logger.warning(f"Failed to process row for subject_id {row.get('subject_ids')}: {e}")

        # Compute votes / most common annotation
        if votes:
            for subject in subjects_dict.values():
                if subject.annotations:
                    flat_annotations = [json.dumps(a) for a in subject.annotations]
                    counter = Counter(flat_annotations)
                    most_common_str, count = counter.most_common(1)[0]
                    subject.most_common_annotation = json.loads(most_common_str)
                    subject.votes = count

        results = SubjectSetResults(
            subjects=list(subjects_dict.values()),
            total_subjects=total,
            retired_subjects=retired_count
        )

        return results

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
        self.annotations:AnnotationsComponent = AnnotationsComponent(self)

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
        return cls(project_id, username, password)

    def connect(self):
        """Conecta a Zooniverse usando las credenciales proporcionadas."""
        pc.Panoptes.connect(username=self.username, password=self.password)

