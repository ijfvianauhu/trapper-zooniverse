from datetime import datetime
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional, List, Any, Dict, Literal
from pydantic import BaseModel, Field

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import yaml

from trapper_zooniverse.i18n import _


@dataclass()
class Report:
    """
    Class to record the result of a media upload process.
    Each identifier (e.g., image, subject, or file) can have multiple
    actions with associated successes or errors.
    """
    title: str
    start_time: datetime = field(default_factory=datetime.now)
    end_time: Optional[datetime] = None

    errors: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)
    successes: Dict[str, List[Dict[str, Any]]] = field(default_factory=dict)

    # -----------------------------
    # ✅ Add an error
    # -----------------------------
    def add_error(self, identifier: str, action: str, message: str, **extra: Any) -> None:
        """Adds an error related to a specific identifier and action."""
        entry = {"action": action, "message": message, **extra}
        self.errors.setdefault(identifier, []).append(entry)

    # -----------------------------
    # ✅ Add a success
    # -----------------------------
    def add_success(self, identifier: str, action: str, **extra: Any) -> None:
        """Adds a success related to a specific identifier and action."""
        entry = {"action": action, **extra}
        self.successes.setdefault(identifier, []).append(entry)

    # -----------------------------
    # ✅ Finish report
    # -----------------------------
    def finish(self) -> None:
        """Marks the report as finished by setting the end time."""
        self.end_time = datetime.now()

    # -----------------------------
    # ✅ Determine report status
    # -----------------------------
    def get_status(self) -> str:
        """Returns the overall status of the report."""
        has_errors = any(self.errors.values())
        has_successes = any(self.successes.values())

        if has_successes and not has_errors:
            return "success"
        elif has_errors and not has_successes:
            return "failed"
        elif has_errors and has_successes:
            return "partial"
        else:
            return "empty"

    # -----------------------------
    # ✅ Get entries filtered by action
    # -----------------------------
    def get_by_action(self, action: str) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
        """
        Returns all errors and successes corresponding to a specific action.
        """
        filtered_errors = {
            identifier: [err for err in entries if err.get("action") == action]
            for identifier, entries in self.errors.items()
            if any(err.get("action") == action for err in entries)
        }

        filtered_successes = {
            identifier: [succ for succ in entries if succ.get("action") == action]
            for identifier, entries in self.successes.items()
            if any(succ.get("action") == action for succ in entries)
        }

        return {"errors": filtered_errors, "successes": filtered_successes}

    # -----------------------------
    # ✅ NEW: Get all unique actions
    # -----------------------------
    def get_actions(self) -> List[str]:
        """
        Returns a sorted list of all distinct actions
        found in both errors and successes.

        Example:
            >>> report.get_actions()
            ['upload', 'validate', 'convert']
        """
        actions = set()

        for entries in list(self.errors.values()) + list(self.successes.values()):
            for e in entries:
                if "action" in e and e["action"]:
                    actions.add(e["action"])

        return sorted(actions)

    # -----------------------------
    # ✅ Summary
    # -----------------------------
    def summary(self) -> str:
        """Returns a readable summary of the report."""
        duration = None
        if self.end_time:
            duration = (self.end_time - self.start_time).total_seconds()

        total_errors = sum(len(v) for v in self.errors.values())
        total_successes = sum(len(v) for v in self.successes.values())

        summary_lines = [
            _(f"Report '{self.title}'"),
            _(f"  Start: {self.start_time}"),
            _(f"  End: {self.end_time or 'in progress'}"),
            _(f"  Status: {self.get_status()}"),
        ]
        if duration:
            summary_lines.append(_(f"  Duration: {duration:.2f}s"))
        summary_lines.append(_(f"  Successes: {total_successes}"))
        summary_lines.append(_(f"  Errors: {total_errors}"))

        return "\n".join(summary_lines)

    # -----------------------------
    # ✅ Load from YAML
    # -----------------------------
    @classmethod
    def from_yaml(cls, filepath: Path) -> "Report":
        """Creates a Report instance from a YAML file."""
        with open(filepath, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
        return cls(**data)

    # -----------------------------
    # ✅ Save to YAML
    # -----------------------------
    def to_yaml(self, filepath: Path):
        """Saves the Report instance to a YAML file."""
        data = asdict(self)
        with open(filepath, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
        return filepath


@dataclass()
class UploadCollectionReport(Report):
    def __init__(self, collection_name: str):
        super().__init__(title='{collection_name}')


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