from pathlib import Path, PosixPath
from typing import Union, List, Optional, Dict, Any, Callable
from trapper_zooniverse.ZooniverseClient import UploadReport
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn, ProgressColumn, TaskID
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing import List
from panoptes_client import Subject, SubjectSet
import logging
import typer
from pydantic import BaseModel
from dataclasses import asdict
import yaml

class TyperUtils:
    console = Console()
    logger = logging.getLogger(__name__)

    @staticmethod
    def info(message: str):
        TyperUtils.console.print(f"[blue]:information:[/blue] {message}")
        TyperUtils.logger.info(message)

    @staticmethod
    def warning(message: str):
        TyperUtils.console.print(f"[orange]:warning:[/orange] {message}")
        TyperUtils.logger.warning(message)

    @staticmethod
    def error(message: str):
        TyperUtils.console.print(f"[red]:cross_mark:[/red] {message}")
        TyperUtils.logger.error(message)

    @staticmethod
    def fatal(message: str):
        TyperUtils.console.print(f"[red]:skull:[/red] {message}")
        TyperUtils.logger.critical(message)
        raise typer.Exit(code=1)

    @staticmethod
    def success(message: str):
        TyperUtils.console.print(f"[green]:white_check_mark:[/green] {message}")
        TyperUtils.logger.info(message)

    @staticmethod
    def validate_yaml_file(path: Path):
        import yaml
        try:
            with open(path, 'r') as file:
                yaml.safe_load(file)
            return True
        except yaml.YAMLError as e:
            raise ValueError((f"YAML file '{str(Path)}' is invalid: {e}"))
        except FileNotFoundError:
            raise ValueError((f"YAML file '{str(Path)}' not found."))


    @staticmethod
    def run_tasks_with_progress(tasks: List[Dict[str, Any]]):
        results = []

        with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                TimeElapsedColumn(),
        ) as progress:

            task_ids: Dict[str, int] = {}
            for t in tasks:
                desc = t.get("description", "Unnamed task")
                task_ids[desc] = progress.add_task(desc, total=1)

            for t in tasks:
                desc = t.get("description", "Unnamed task")
                func: Callable = t["func"]
                args = t.get("args", ())
                kwargs = t.get("kwargs", {})

                progress.update(task_ids[desc], description=f"[cyan]{desc}[/cyan] (running)")
                try:
                    result = func(*args, **kwargs)
                    results.append(result)
                    progress.update(task_ids[desc], advance=1, description=f"[green]{desc}[/green] (done)")
                except Exception as e:
                    progress.update(task_ids[desc], description=f"[red]{desc}[/red] (failed)")
                    TyperUtils.error(f"Error in task '{desc}': {e}")
                    raise

        return results

    @staticmethod
    def select_from_list(
            items: List[Any],
            title: str = "Select an item",
            show_id: bool = True,
            show_name: bool = True,
            success_msg: str = "Selected item"
    ) -> Any:
        """
        Allows the user to select an item from a list. If only one item exists, it is automatically selected.
        Otherwise, a table is displayed and the user is prompted to choose.

        Parameters
        ----------
        items : List[Any]
            List of objects to select from. Objects must have 'id' and 'name' attributes if show_id or show_name are True.
        title : str, optional
            Title of the selection table.
        show_id : bool, optional
            Whether to show the 'ID' column in the table.
        show_name : bool, optional
            Whether to show the 'Name' column in the table.
        success_msg : str, optional
            Message displayed when a single item is automatically selected.

        Returns
        -------
        Any
            The selected item from the list.
        """
        if not items:
            return None

        if len(items) == 1:
            TyperUtils.success(f"{success_msg}: {items[0].name}")
            return items[0]

        # Crear tabla
        table = Table(title=title, show_lines=True)
        table.add_column("Index", justify="right", style="cyan", no_wrap=True)
        if show_id:
            table.add_column("ID", justify="right", style="yellow")
        if show_name:
            table.add_column("Name", style="green")

        for i, item in enumerate(items, start=1):
            row = [str(i)]
            if show_id:
                row.append(str(item.id))
            if show_name:
                row.append(item.name)
            table.add_row(*row)

        TyperUtils.console.print(table)

        # Pedir al usuario que elija
        choice = Prompt.ask(
            f"[bold cyan]Enter the number of the item you want to select[/bold cyan]",
            choices=[str(i) for i in range(1, len(items) + 1)],
            show_choices=False
        )

        return items[int(choice) - 1]

    @staticmethod
    def show_subject_sets_table(subject_sets: list[SubjectSet]):
        """Muestra una tabla con los SubjectSets de Zooniverse."""
        table = Table(title="Zooniverse Subject Sets", show_lines=True)

        # Define las columnas
        table.add_column("ID", justify="right", style="cyan", no_wrap=True)
        table.add_column("Name", style="green")
        table.add_column("Created", style="yellow")
        table.add_column("Updated", style="magenta")
        table.add_column("Subjects Count", justify="right", style="blue")

        for ss in subject_sets:
            # Algunos SubjectSets pueden no tener todos los campos
            created = getattr(ss, "created_at", "—")
            updated = getattr(ss, "updated_at", "—")
            name = getattr(ss, "display_name", "—")
            subject_count = getattr(ss, "set_member_subjects_count", "—")

            table.add_row(
                str(ss.id),
                name,
                str(created),
                str(updated),
                str(subject_count)
            )

        TyperUtils.console.print(table)


    @staticmethod
    def show_subjects_table(subjects: List[Subject], title: str = "Subjects"):
        """
        Display a list of Zooniverse Subjects in a table, and show available metadata and location keys.

        Parameters
        ----------
        subjects : List[Subject]
            List of Subject objects.
        title : str
            Title for the table.
        """
        if not subjects:
            TyperUtils.warning(f"[yellow]No subjects to display in '{title}'[/yellow]")
            return

        table = Table(title=title, show_lines=True)
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Metadata", style="green")
        table.add_column("Locations", style="magenta")

        all_metadata_keys = set()
        all_location_keys = set()

        for subj in subjects:
            # Metadata
            metadata = getattr(subj, "metadata", {})
            metadata_str = ", ".join(f"{k}: {v}" for k, v in metadata.items())
            all_metadata_keys.update(metadata.keys())

            # Locations
            locations = getattr(subj, "locations", [])
            locations_str = ", ".join(
                f"{k}: {v}" for loc in locations if isinstance(loc, dict) for k, v in loc.items()
            )
            for loc in locations:
                if isinstance(loc, dict):
                    all_location_keys.update(loc.keys())

            # Añadir fila de cada subject
            table.add_row(str(subj.id), metadata_str, locations_str)

        # Añadir fila final con atributos disponibles
        table.add_row(
            "[bold yellow]Available Keys[/bold yellow]",
            ", ".join(sorted(all_metadata_keys)) if all_metadata_keys else "—",
            ", ".join(sorted(all_location_keys)) if all_location_keys else "—",
        )

        TyperUtils.console.print(table)
        TyperUtils.info(f"Total: {len(subjects)}")

    def show_objects_table(objects: List[Any], title: str = "Objects Table"):
        """
        Displays a table with all public attributes of the given objects.

        Parameters
        ----------
        objects : List[Any]
            List of objects to display in a table. All public attributes will be used as columns.
        title : str, optional
            Title of the table.
        """
        if not objects:
            TyperUtils.warning(f"[yellow]No objects to display in table '{title}'")
            return

        # Obtener atributos públicos del primer objeto
        first_obj = objects[0]
        attrs = [attr for attr in dir(first_obj) if not attr.startswith("_") and not callable(getattr(first_obj, attr))]

        table = Table(title=title, show_lines=True)

        # Crear columnas dinámicamente
        for attr in attrs:
            table.add_column(attr, style="green")

        # Añadir filas
        for obj in objects:
            row = [str(getattr(obj, attr, "—")) for attr in attrs]
            table.add_row(*row)

        TyperUtils.console.print(table)

    @staticmethod
    def validate_zip_file(path: Path):
        import zipfile
        try:
            with zipfile.ZipFile(path, 'r') as zip_ref:
                bad_file = zip_ref.testzip()
                if bad_file is not None:
                    raise ValueError(f"ZIP file '{Path}' is corrupted at file '{bad_file}'.")

        except zipfile.BadZipFile:
            raise ValueError(f"ZIP file '{Path}' is not a zip file or it is corrupted.")
        except FileNotFoundError:
            raise ValueError(f"ZIP file '{Path}' not found.")

    @staticmethod
    def display_report(report: UploadReport):
        """Muestra el informe formateado en consola con Rich."""
        title = Text(f"📊 Upload Report: {report.subjectset_name}", style="bold cyan")
        TyperUtils.console.rule(title)

        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Metric", style="bold yellow")
        table.add_column("Count", justify="right", style="bold white")

        stats = {
            "Uploaded images": len(report.uploaded_images),
            "Failed uploads": len(report.failed_uploads),
            "Skipped (human)": len(report.skipped_human),
            "Skipped (private)": len(report.skipped_private),
            "Downloaded": len(report.download_images),
            "Download failed": len(report.download_failed),
        }

        for key, value in stats.items():
            table.add_row(key, str(value))

        TyperUtils.console.print(Panel.fit(
            f"Start: [green]{report.start_time}[/green]\n"
            f"End:   [green]{report.end_time}[/green]",
            title="🕒 Timestamps",
            border_style="cyan"
        ))

        TyperUtils.console.print(table)
        TyperUtils.console.rule()

    @staticmethod
    def save_yaml(report: UploadReport, filename: PosixPath = None):
        """Guarda el informe en un archivo YAML."""
        if not filename:
            timestamp = report.start_time.replace(":", "-").replace("T", "_")
            filename = f"upload_report_{timestamp}.yaml"

        with open(filename, "w", encoding="utf-8") as f:
            yaml.safe_dump(asdict(report), f, sort_keys=False, allow_unicode=True)

    @staticmethod
    def load_yaml(filename: str):
        """Carga un informe desde un archivo YAML."""
        with open(filename, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)

        return UploadReport(**data)

    @staticmethod
    def json2Table(
            data: Union[BaseModel, List[dict]],
            columns: Optional[List[str]] = None,
            title: str = "Table"
    ):
        """
        Convert a Pydantic BaseModel or a list of dicts to a Rich table and print it.

        Parameters
        ----------
        data : BaseModel | list[dict]
            Pydantic model containing 'results' or a plain list of dictionaries.
        columns : list[str], optional
            List of columns to display. Defaults to all keys of the first row.
        title : str, optional
            Table title. Defaults to "Table".
        """
        # Extraer filas
        if isinstance(data, BaseModel):
            rows = [item.model_dump() for item in getattr(data, "results", [data])]
        elif isinstance(data, list):
            rows = data
        else:
            raise ValueError("Data must be a Pydantic BaseModel or a list of dicts")

        if not rows:
            TyperUtils.console.print("No data to display")
            return

        # Determinar columnas
        if columns is None:
            columns = list(rows[0].keys())

        # Crear tabla
        table = Table(title=title)
        for col in columns:
            table.add_column(col, justify="left")

        # Añadir filas
        for row in rows:
            table.add_row(*[str(row.get(col, "")) for col in columns])

        TyperUtils.console.print(table)

        # Mostrar los campos disponibles
        available_fields = list(rows[0].keys())
        TyperUtils.console.print(
            f"[dim]Available fields:[/dim] [cyan]{', '.join(available_fields)}[/cyan]"
        )
