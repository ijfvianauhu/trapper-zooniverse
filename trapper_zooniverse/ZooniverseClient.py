import os
import time
import logging
from collections import defaultdict
from datetime import datetime
from itertools import count
from typing import List, Tuple, Optional, Union, Dict
import json
import panoptes_client as pc
import requests
from panoptes_client import SubjectSet, Subject, Project, Workflow, ProjectRole, User, Classification, Panoptes
from trapper_zooniverse.Schemas import SubjectSetResults

from trapper_zooniverse.i18n import setup_i18n, _

class ZooniverseClientComponent:
    def __init__(self, client = None):
        self.client = client


#
# Workflow
#
#

class WorkflowsComponent(ZooniverseClientComponent):

    def get_all(self) -> List[Workflow]:
        project = Project.find(self.client.project_id)
        workflows = Workflow.where(project_id=project.id)
        return list(workflows)

    def get_by_id(self, id:int) -> Workflow:
        self.client.connect()
        return Workflow.find(id)

    def get_by_subjectset(self, subjectset_id:int) -> List[Workflow]:
        subject_set = SubjectSet.find(subjectset_id)
        workflow_ids = subject_set.raw["links"].get("workflows", [])
        workflows = [Workflow.find(wid) for wid in workflow_ids]

        return list(workflows)
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

    def get_subject_sets_from_workflow(self, workflow_id: int) -> List[SubjectSet]:
        """
        Retrieves all subject sets linked to a specific workflow in Zooniverse.

        Parameters
        ----------
        workflow_id : int
            The ID of the workflow whose subject sets will be retrieved.

        Returns
        -------
        List[SubjectSet]
            A list of `SubjectSet` objects associated with the workflow.

        Raises
        ------
        ConnectionError
            If the client is not connected to Zooniverse or the request fails.
        ValueError
            If the workflow ID is missing, invalid, or not found.

        Notes
        -----
        This method uses the Zooniverse API to fetch subject sets linked to
        the given workflow. Each workflow can have one or more associated subject sets.
        """

        project = Project.find(self.client.project_id)
        subject_sets = SubjectSet.where(project_id=project.id)

        res = []
        for ss in subject_sets:
            if str(workflow_id) in  ss.raw.get("links").get("workflows", []):
                res.append(ss)

        return res

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

    def get_by_id(self, id) -> List:
        return Subject.find(id)

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


# AnnotationsComponent
#

class AnnotationsComponent(ZooniverseClientComponent):

    @staticmethod
    def calculate_annotations_summary(data):
        from collections import Counter

        for workflow_key, subjects in data.items():
            for sid, classifications in subjects.items():
                all_choices = []

                # Recorrer cada clasificación
                for cl in classifications:
                    for ann in cl.get("annotations", []):
                        for val in ann.get("value", []):
                            # 'val' puede ser un dict con 'choice' si es un task tipo multiple choice
                            if isinstance(val, dict) and "choice" in val:
                                all_choices.append(val["choice"])
                            elif isinstance(val, str):
                                all_choices.append(val)

                # Contar apariciones
                choice_counts = Counter(all_choices)
                if choice_counts:
                    # Elección mayoritaria
                    majority_choice = choice_counts.most_common(1)[0][0]
                else:
                    majority_choice = None

                # Guardar resumen dentro de cada subject
                summary = {
                    "all_choices": dict(choice_counts),
                    "majority_choice": majority_choice
                }

                # Si quieres, puedes añadirlo al diccionario de cada subject
                # Si las clasificaciones están en lista:
                subjects[sid + "_summary"] = summary

    @staticmethod
    def _safe_load_json(value: str, default=None):
        if default is None:
            default = []
        if not value:
            return default
        try:
            return json.loads(value)
        except Exception:
            try:
                return json.loads(value.replace("'", '"'))
            except Exception:
                return default

    @staticmethod
    def _parse_subject_ids(value: str) -> List[int]:
        """Normaliza varios formatos comunes y devuelve lista de ints."""
        if value is None:
            return []
        v = value.strip()
        if v == "":
            return []
        # Caso típico "123" o "123,456"
        if "," in v:
            parts = [p.strip() for p in v.split(",") if p.strip()]
        # Caso forma JSON "['123','456']" o "[123,456]"
        elif v.startswith("[") and v.endswith("]"):
            try:
                parsed = json.loads(v.replace("'", '"'))  # reemplaza comillas simples
                parts = [str(x).strip() for x in parsed]
            except Exception:
                parts = [v.strip("[] \t\n'\"")]
        else:
            parts = [v]
        ids = []
        for p in parts:
            try:
                ids.append(int(p))
            except ValueError:
                # intenta extraer dígitos si hay ruido
                digits = ''.join(ch for ch in p if ch.isdigit())
                if digits:
                    ids.append(int(digits))
        return ids

    def get_export_dates_by_project(self) -> Dict[str, Optional[str]]:
        """
        Devuelve las fechas del último export disponible por tipo (classifications, subjects, etc.)
        para un proyecto de Zooniverse.

        Parameters
        ----------
        project_id : str
            ID del proyecto en Zooniverse.

        Returns
        -------
        Dict[str, Optional[str]]
            Diccionario con las fechas ISO de los últimos exports o '—' si no existen.
        """
        project = Project.find(self.client.project_id)
        base_url = "https://panoptes.zooniverse.org/api/projects"
        print(project.get_export(export_type="classifications", wait=False))
        exit(1)

        panoptes = getattr(Panoptes, "_instance", None)
        session = getattr(panoptes, "session", None) if panoptes else None
        headers = session.headers if session else {}

        # Tipos posibles de export
        export_types = [
            "classifications",
            "subjects",
            "aggregations",
            "workflow_contents",
            "subject_sets",
        ]

        export_dates = {t: "—" for t in export_types}

        for export_type in export_types:
            url = f"{base_url}/{project.id}/exports/{export_type}"
            response = requests.get(url, headers=headers)
            print(url)
            print(response)
            if response.status_code == 200:
                data = response.json()
                print(data)
                # El export puede estar vacío si nunca se generó
                if "exports" in data and data["exports"]:
                    created_at = data["exports"][0].get("created_at")
                    if created_at:
                        try:
                            dt = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            export_dates[export_type] = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception as e:
                            print(e)
                            export_dates[export_type] = created_at

        return export_dates

    def get_last_exports_date_by_workflow(self) -> List[Tuple[int, str, Union[str, None]]]:
        """
        Devuelve la fecha del último export de clasificaciones por cada workflow del proyecto.

        Returns
        -------
        List[Tuple[int, str, str]]
            Lista de tuplas con (workflow_id, workflow_name, last_export_date o '-')
        """
        project = Project.find(self.client.project_id)
        workflows = Workflow.where(project_id=project.id)
        results = []

        for wf in workflows:
            try:
                export = wf.get_export("classifications", wait=False)
                if export:
                    # La fecha puede venir en export.metadata['updated_at'] o 'created_at'
                    metadata = getattr(export, "raw", {}).get("metadata", {})
                    last_export_date = (
                        metadata.get("updated_at")
                        or metadata.get("created_at")
                        or "-"
                    )

                    # Normaliza formato
                    if last_export_date != "-":
                        try:
                            dt = datetime.fromisoformat(last_export_date.replace("Z", "+00:00"))
                            last_export_date = dt.strftime("%Y-%m-%d %H:%M:%S")
                        except Exception:
                            pass

                    results.append((wf.id, wf.display_name or "—", last_export_date))
                    self.client.logger.debug(
                        f"Workflow {wf.display_name} export last updated at {last_export_date}"
                    )
                else:
                    results.append((wf.id, wf.display_name or "—", "-"))
                    self.client.logger.debug(f"Workflow {wf.display_name} has no export.")
            except Exception as e:
                self.client.logger.debug(f"Workflow {wf.display_name} error getting export: {e}")
                results.append((wf.id, wf.display_name or "—", "-"))

        return results

    def get_all(self) ->List[Tuple[int, Optional[str]]]:
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

    def get_by_workflow(self, workflow_id: int, generate: bool=False) -> List[dict]:

        workflow = Workflow.find(workflow_id)

        if generate:
            export = workflow_id.get_export('classifications', egenerate=True)
        else:
            export = workflow_id.get_export('classifications', wait=True, wait_timeout=600)

        reader = export.csv_dictreader()
        rows = list(reader)

        annotations_data = []
        for row in rows:
            annotations = AnnotationsComponent._safe_load_json(row.get('annotations', '[]'), default=[])
            annotations_data.append({
                "classification_id": row.get('classification_id'),
                "user_name": row.get('user_name'),
                "user_id": row.get('user_id'),
                "subject_ids": AnnotationsComponent._parse_subject_ids(row.get('subject_ids', "")),
                "annotations": annotations
            })

        return annotations_data

    def get_by_subjectset(self, subjectset_id: int, votes: bool=True) -> SubjectSetResults:
        """
        Fetches the results of all subjects in a SubjectSet as Pydantic models.

        :param subject_set_id: Zooniverse SubjectSet ID
        :param votes: If True, calculate the most , wait_timeout=600common annotation per subject
        :return: SubjectSetResults
        """

        def fix_encoding(s):
            if isinstance(s, str):
                try:
                    return s.encode("latin1").decode("utf-8")
                except Exception:
                    return s
            elif isinstance(s, dict):
                return {fix_encoding(k): fix_encoding(v) for k, v in s.items()}
            elif isinstance(s, list):
                return [fix_encoding(x) for x in s]
            return s

        subject_set = SubjectSet.find(subjectset_id)

        try:
            export=subject_set.get_export('classifications')
        except Exception:
            export = subject_set.generate_export('classifications')
        # message = f"No existing {export_type} export found for {object_type} {obj.id}. Generating new one..."

        from collections import defaultdict

        reader = export.csv_dictreader()
        # Fix utf-8 encoding issues
        rows = fix_encoding(list(export.csv_dictreader()))

        results = defaultdict(lambda: {"summary": {"total_subjects": 0, "retired_subjects": 0},
                                       "data": defaultdict(list)})
        for row in rows:
            wname = row.get('workflow_name') or 'unknown_workflow'
            wid = row.get('workflow_id') or 'unknown_id'
            wver = row.get('workflow_version') or ''
            workflow_key = f"{wid}:{wname}:{wver}"

            subject_ids = AnnotationsComponent._parse_subject_ids(row.get('subject_ids', ""))

            # --- Nombre del subject (si existe en metadata o subject_data)

            subject_data_raw = row.get("subject_data") or ""
            subject_data_parsed = {}
            if subject_data_raw:
                try:
                    subject_data_parsed = json.loads(subject_data_raw)
                except Exception:
                    # Algunos exports usan comillas simples o están mal escapados
                    try:
                        subject_data_parsed = json.loads(subject_data_raw.replace("'", '"'))
                    except Exception:
                        subject_data_parsed = {}

            for sid in subject_ids:
                results[workflow_key]["summary"]["total_subjects"] += 1

                sid_str = str(sid)
                subdata = subject_data_parsed.get(sid_str, {})

                # Intentar deducir un nombre legible
                subject_name = None
                for k in ("filename", "Filename", "file_name", "name", "display_name"):
                    if isinstance(subdata, dict) and k in subdata:
                        subject_name = subdata[k]
                        break

                # get MEDIA_ID

                def get_media_id(s:str):
                    import re

                    s = "R0034/R0034-DONA_0066/R0034-DONA_0066__20250101_7436.JPG"

                    # 1️⃣ Última parte del path
                    filename = s.split('/')[-1]
                    #print(filename)  # R0034-DONA_0066__20250101_7436.JPG

                    # 2️⃣ Número después de __
                    match = re.search(r'__(\d+)', filename)
                    number = match.group(1) if match else None
                    return number

                media_id = get_media_id(subject_name)

                if not subject_name:
                    # Si no encontramos un nombre, guardamos el subdata completo
                    subject_name = json.dumps(subdata, ensure_ascii=False)

                # --- Retired y razón de retiro
                retired_info = subdata.get("retired", {})
                is_retired = bool(retired_info)  # True si hay un objeto de retired
                retirement_reason = retired_info.get("retirement_reason") if is_retired else None

                if is_retired:
                    results[workflow_key]["summary"]["retired_subjects"] += 1

                annotations = AnnotationsComponent._safe_load_json(row.get('annotations', '[]'), default=[])

                classification_info = {
                    "classification_id": row.get('classification_id'),
                    "user_name": row.get('user_name'),
                    "user_id": row.get('user_id'),
                    "subject_name": subject_name,
                    "retired": is_retired,
                    "retirement_reason" : retirement_reason,
                    "annotations": annotations
                }

                results[workflow_key]["data"][f"{sid}:{media_id}"].append(classification_info)

        return SubjectSetResults(workflows=results)

    def _get_or_generate_export(self, obj, export_type: str = "classifications", wait: bool = True, timeout: int = 600):
        """
        Obtiene (o genera si no existe) un export para un objeto de Zooniverse
        (Project, Workflow o SubjectSet).

        Parameters
        ----------
        obj : Project | Workflow | SubjectSet
            Objeto de Zooniverse (ya obtenido con Panoptes).
        export_type : str
            Tipo de export ("classifications", "subjects", etc.)
        wait : bool
            Si True, espera hasta que el export esté disponible.
        timeout : int
            Tiempo máximo de espera en segundos.

        Returns
        -------
        dict
            {
                "id": int,
                "type": str,
                "object_type": str,
                "ready": bool,
                "url": str | None,
                "created_at": datetime | None,
                "message": str
            }
        """
        if isinstance(obj, Project):
            object_type = "Project"
        elif isinstance(obj, Workflow):
            object_type = "Workflow"
        elif isinstance(obj, SubjectSet):
            object_type = "SubjectSet"
        else:
            raise TypeError("El objeto debe ser Project, Workflow o SubjectSet")

        export = None
        message = f"Checking for existing {export_type} export for {object_type} {obj.id}..."

        # Intentar obtener un export existente
        try:
            export = obj.get_export(export_type, wait=False)
            message = f"Found existing {export_type} export for {object_type} {obj.id}."
        except Exception:
            message = f"No existing {export_type} export found for {object_type} {obj.id}. Generating new one..."

        print(message)
        # Si no existe, generarlo
        if not export or isinstance(export, dict) or not hasattr(export, "url"):
            try:
                export = obj.generate_export(export_type, wait=False)
                message = f"Generated new {export_type} export for {object_type} {obj.id}."
            except Exception as e:
                return {
                    "id": obj.id,
                    "object_type": object_type,
                    "type": export_type,
                    "ready": False,
                    "url": None,
                    "created_at": None,
                    "message": f"Error generating export: {e}"
                }

        # Si lo que tenemos es una Response (HTTP)
        print(export.__dict__)
        if hasattr(export, "json"):
            try:
                export_data = export.json()
                url = export_data.get("url")
                created_at = export_data.get("created_at")
            except Exception:
                url = None
                created_at = None
        else:
            url = getattr(export, "url", None)
            created_at = getattr(export, "created_at", None)

        # Esperar si es necesario
        if wait and hasattr(export, "ready"):
            start = time.time()
            while not export.ready and (time.time() - start < timeout):
                time.sleep(10)
                export.reload()

        if isinstance(created_at, str):
            created_at = datetime.fromisoformat(created_at.replace("Z", "+00:00"))

        return {
            "id": obj.id,
            "object_type": object_type,
            "type": export_type,
            "ready": getattr(export, "ready", bool(url)),
            "url": url,
            "created_at": created_at,
            "message": message if url else f"{message} (still processing)"
        }

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
        self.workflows: WorkflowsComponent = WorkflowsComponent(self)

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

    def _get_current_user_role(self, project_id: int) -> list[str]:
        """
        Devuelve una lista con los roles del usuario autenticado en un proyecto.
        Si no tiene roles, devuelve una lista vacía.
        """
        # Obtener el usuario autenticado
        current_user = User.me()
        current_user_id = str(current_user.id)

        roles = []

        # Buscar todos los roles del proyecto
        for pr in ProjectRole.where(project_id=project_id):
            links = pr.raw.get("links", {})

            for role_type, user_info in links.items():
                if role_type == "project":
                    continue

                user_id = user_info.get("id")
                if user_id == current_user_id:
                    roles.append(role_type)

        return roles

