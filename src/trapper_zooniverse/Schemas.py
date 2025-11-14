from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field

@dataclass()
class UploadAnnotationsReport:
    """
    Clase para registrar el resultado de un proceso de subida de anotaciones.
    Cada identificador (por ejemplo, imagen, subject o fichero) puede tener múltiples errores o éxitos asociados.
    """
    subjectset_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    errors: Dict[str, List[Any]] = field(default_factory=dict)
    successes: Dict[str, List[Any]] = field(default_factory=dict)

    def add_error(self, identifier: str, error: Any) -> None:
        """Agrega un error asociado a un identificador."""
        if identifier not in self.errors:
            self.errors[identifier] = []
        self.errors[identifier].append(error)

    def add_success(self, identifier: str, success: Any) -> None:
        """Agrega un éxito asociado a un identificador."""
        if identifier not in self.successes:
            self.successes[identifier] = []
        self.successes[identifier].append(success)

    def finish(self) -> None:
        """Marca la fecha/hora de finalización."""
        self.end_time = datetime.now()

    def summary(self) -> str:
        """Devuelve un resumen legible del reporte."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        total_errors = sum(len(v) for v in self.errors.values())
        total_successes = sum(len(v) for v in self.successes.values())

        summary_lines = [
            f"UploadAnnotationsReport for subject set '{self.subjectset_name}'",
            f"  Inicio: {self.start_time}",
            f"  Fin: {self.end_time or 'en curso'}",
        ]
        if duration:
            summary_lines.append(f"  Duración: {duration:.2f}s")
        summary_lines.append(f"  Éxitos: {total_successes}")
        summary_lines.append(f"  Errores: {total_errors}")

        return "\n".join(summary_lines)

    @classmethod
    def from_yaml(cls, filepath: Path) -> "UploadAnnotationsReport":
        """Crea una instancia de UploadAnnotationsReport a partir de un archivo YAML."""
        import yaml

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return UploadAnnotationsReport(**data)


@dataclass()
class UploadMediaReport:
    """
    Clase para registrar el resultado de un proceso de subida de anotaciones.
    Cada identificador (por ejemplo, imagen, subject o fichero) puede tener múltiples errores o éxitos asociados.
    """
    subjectset_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    errors: Dict[str, List[Any]] = field(default_factory=dict)
    successes: Dict[str, List[Any]] = field(default_factory=dict)

    def add_error(self, identifier: str, error: Any) -> None:
        """Agrega un error asociado a un identificador."""
        if identifier not in self.errors:
            self.errors[identifier] = []
        self.errors[identifier].append(error)

    def add_success(self, identifier: str, success: Any) -> None:
        """Agrega un éxito asociado a un identificador."""
        if identifier not in self.successes:
            self.successes[identifier] = []
        self.successes[identifier].append(success)

    def finish(self) -> None:
        """Marca la fecha/hora de finalización."""
        self.end_time = datetime.now()

    def summary(self) -> str:
        """Devuelve un resumen legible del reporte."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        total_errors = sum(len(v) for v in self.errors.values())
        total_successes = sum(len(v) for v in self.successes.values())

        summary_lines = [
            f"UploadAnnotationsReport for subject set '{self.subjectset_name}'",
            f"  Inicio: {self.start_time}",
            f"  Fin: {self.end_time or 'en curso'}",
        ]
        if duration:
            summary_lines.append(f"  Duración: {duration:.2f}s")
        summary_lines.append(f"  Éxitos: {total_successes}")
        summary_lines.append(f"  Errores: {total_errors}")

        return "\n".join(summary_lines)

    @classmethod
    def from_yaml(cls, filepath: Path) -> "UploadMediaReport":
        """Crea una instancia de UploadAnnotationsReport a partir de un archivo YAML."""
        import yaml

        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return UploadMediaReport(**data)

    def to_yaml(self, filepath: Path = None) -> Path:
        import yaml

        """Saves the UploadAnnotationsReport instance to a YAML file."""
        if filepath is None:
            timestamp = str(self.start_time).replace(":", "-").replace("T", "_")
            filepath = Path(f"upload_report_{timestamp}.yaml")

        data = asdict(self)

        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)

        return filepath



@dataclass
class UploadReport:
    subjectset_name: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None
    uploaded_images: List[str] = field(default_factory=list)
    failed_uploads: List[str] = field(default_factory=list)
    skipped_human: List[Dict] = field(default_factory=list)
    skipped_private: List[Dict] = field(default_factory=list)
    download_images: List[str] = field(default_factory=list)
    download_failed: List[Dict] = field(default_factory=list)

    def finish(self) -> None:
        """Marca la fecha/hora de finalización."""
        self.end_time = datetime.now()

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

class ClassificationInfo(BaseModel):
    """Información de una clasificación individual hecha por un usuario en Zoo."""
    classification_id: Optional[str]
    user_name: Optional[str]
    user_id: Optional[str]
    annotations: List[Any] = Field(default_factory=list)
    subject_name: Optional[str]
    retired: bool = False
    retirement_reason: Optional[str] = None

class Zoo2TrapperObservation(BaseModel):
    """Anotacion individual extraída de zoo para poder ser importada en Trapper."""
    observationType: Literal["animal", "human", "vehicle", "black", "unclassified", "unknown"]
    scientificName: Optional[str] = None
    count: Optional[int] = None
    countNew: Optional[int] = None
    lifeStage: Optional[str] = None
    sex: Optional[str] = None
    behavior: Optional[str] = None
    individualID: Optional[str] = None
    observationTags: Optional[str] = None

class WorkflowSummary(BaseModel):
    """Resumen general de un workflow."""
    total_subjects: int = 0
    retired_subjects: int = 0
    retired_pct: Optional[float] = None

class WorkflowData(BaseModel):
    """Datos y resumen asociados a un workflow."""
    summary: WorkflowSummary
    data: Dict[str, List[ClassificationInfo]]

class SubjectSetResults(BaseModel):
    """Resultado completo del SubjectSet agrupado por workflow."""
    workflows: Dict[str, WorkflowData]
