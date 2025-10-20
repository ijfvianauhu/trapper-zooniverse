import json
from pathlib import Path, PosixPath
from typing import Union, List, Optional, Dict, Any, Callable, Tuple

from rich.markdown import Markdown
from rich.syntax import Syntax
from rich.tree import Tree

from trapper_zooniverse.Schemas import UploadReport, UploadAnnotationsReport
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn, ProgressColumn, TaskID
from rich.panel import Panel
from rich.text import Text
from rich import box
from typing import List
from panoptes_client import Subject, SubjectSet, Classification
import logging
import typer
from pydantic import BaseModel, HttpUrl
from dataclasses import asdict
import yaml

from trapper_zooniverse.i18n import _
from trapper_zooniverse.ui.typer.ConfigManager import AppConfig


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
    def display_config_table(config: AppConfig, title: str = "Config") -> None:
        console = Console()
        table = Table(title=title, show_lines=False)
        table.add_column("Section", style="cyan", no_wrap=True)
        table.add_column("Field", style="magenta", no_wrap=True)
        table.add_column("Value", style="white")

        for section, field, value in TyperUtils.flatten_model(config):
            table.add_row(section, field, value)

        console.print(table)

    @staticmethod
    def flatten_model(model: BaseModel, section: str = "") -> list[tuple[str, str, str]]:
        """
        Devuelve una lista de tuplas (section, field, value)
        con los campos del modelo Pydantic, incluyendo submodelos.
        """
        items = []
        for field, value in model:
            if isinstance(value, BaseModel):
                # Submodelo: expandir recursivamente
                items.extend(TyperUtils.flatten_model(value, section=field))
            else:
                # Si es SecretStr, ocultar el valor
                #if isinstance(value, SecretStr):
                #    display_value = "**********"
                #else:
                display_value = str(value)
                items.append((section, field, display_value))
        return items

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
    def print_as_json(objects: List[Any]):
        json_str = json.dumps([a.__dict__ for a in objects], indent=2, ensure_ascii=False, default=str)
        TyperUtils.console.print(json_str)

    @staticmethod
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
    def print_reports_in_directory(results_dir: Path):
        """
        List all YAML upload reports saved in the default upload reports directory.
        Shows filename, report title, start/end time, and status.
        """

        yaml_files = sorted(
            results_dir.glob("*.yaml"),
            key=lambda p: p.stat().st_mtime,
            reverse=True,
        )

        if not yaml_files:
            TyperUtils.fatal(f"No upload reports found in{results_dir}")

        table = Table(
            title=f"📊 Upload Reports in {str(results_dir)}",
            box=box.SIMPLE_HEAVY,
            header_style="bold cyan",
        )
        table.add_column("File name", style="cyan", no_wrap=True)
        table.add_column("Title", style="green")
        table.add_column("Start time", style="magenta")
        table.add_column("End time", style="white")
        table.add_column("Status", style="bold")

        for yaml_file in yaml_files:
            try:
                with open(yaml_file, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)

                title = data.get("title", "—")
                start_time = data.get("start_time", "—")
                end_time = data.get("end_time", "—")

                # Determinar estado
                errors = data.get("errors", {})
                successes = data.get("successes", {})

                has_errors = bool(errors)
                has_successes = bool(successes)

                if has_successes and not has_errors:
                    status = "[green]SUCCESS[/green]"
                elif has_errors and not has_successes:
                    status = "[red]FAILED[/red]"
                elif has_errors and has_successes:
                    status = "[yellow]PARTIAL[/yellow]"
                else:
                    status = "[bright_black]EMPTY[/bright_black]"

            except Exception as e:
                title = "⚠️ Error loading"
                start_time = end_time = "—"
                status = f"[red]{str(e)}[/red]"

            table.add_row(yaml_file.name, title, str(start_time), str(end_time), status)

        TyperUtils.console.print(table)

    @staticmethod
    def display_report2(report: "Report", raw: bool = False) -> None:
        """
        Displays a formatted summary of the Report instance in the console using Rich.
        """

        if raw:
            # Mostrar el YAML tabulado
            if isinstance(report, Path):
                # Si se pasa la ruta, cargar el YAML
                with open(report, "r", encoding="utf-8") as f:
                    data = yaml.safe_load(f)
            else:
                # Convertir la instancia Report a diccionario
                from dataclasses import asdict
                data = asdict(report)

            yaml_str = yaml.safe_dump(data, sort_keys=False, allow_unicode=True)
            TyperUtils.console.print(yaml_str)
            return

        title = Text(f"📊 Report: {report.title}", style="bold cyan")
        TyperUtils.console.rule(title)

        time_panel = Panel.fit(
            f"Start: [green]{report.start_time}[/green]\n"
            f"End:   [green]{report.end_time or 'in progress'}[/green]",
            title="🕒 Timestamps",
            border_style="cyan"
        )
        TyperUtils.console.print(time_panel)

        total_errors = sum(len(v) for v in report.errors.values())
        total_successes = sum(len(v) for v in report.successes.values())

        stats = {
            "Total successes": total_successes,
            "Total errors": total_errors,
            "Unique identifiers": len(set(report.errors.keys()) | set(report.successes.keys())),
            "Unique actions": len(report.get_actions()),
            "Status": report.get_status(),
        }

        table = Table(box=box.SIMPLE_HEAVY)
        table.add_column("Metric", style="bold yellow")
        table.add_column("Value", justify="right", style="bold white")

        for key, value in stats.items():
            style = "green" if key == "Status" and value == "success" else "red" if key == "Status" and value == "failed" else "white"
            table.add_row(key, f"[{style}]{value}[/{style}]")

        TyperUtils.console.print(table)

        # -----------------------------
        # ⚙️ Actions summary
        # -----------------------------
        actions = report.get_actions()
        if actions:
            action_table = Table(box=box.SIMPLE)
            action_table.add_column("Action", style="bold magenta")
            action_table.add_column("Successes", justify="right", style="green")
            action_table.add_column("Errors", justify="right", style="red")

            for action in actions:
                action_data = report.get_by_action(action)
                success_count = sum(len(v) for v in action_data["successes"].values())
                error_count = sum(len(v) for v in action_data["errors"].values())
                action_table.add_row(action, str(success_count), str(error_count))

            TyperUtils.console.print(Panel.fit(action_table, title="⚙️ Actions Overview", border_style="magenta"))

        # -----------------------------
        # ✅ Status line
        # -----------------------------
        TyperUtils.console.rule(f"[bold cyan]Report Status: [white]{report.get_status().upper()}[/white]")

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
    def display_upload_annotations_report(report: UploadAnnotationsReport):
        """
        ## display_upload_annotations_report

        Displays a formatted summary of an **UploadAnnotationsReport** in the console using Rich.

        ### 🧩 Behavior
        - Prints a header with the subject set name.
        - Displays general statistics (number of failed and successful annotations).
        - Shows start and end timestamps.
        - Prints up to **10 first subjects with errors** and **10 with successes**,
          each as a Rich table (`Subject` → `Messages`).
          - Each key is a subject ID.
          - Each value is a list of error or success messages.

        ### ⚙️ Parameters
        - `report` (`UploadAnnotationsReport`):
          A Pydantic model containing:
          - `subjectset_name`
          - `start_time`, `end_time`
          - `errors`: dict[str, list[str]] — mapping subjects to error messages
          - `successes`: dict[str, list[str]] — mapping subjects to success messages
        """

        title = Text(f"📊 Upload Annotations Report: {report.subjectset_name}", style="bold cyan")
        TyperUtils.console.rule(title)

        # --- Summary table ---
        summary = Table(box=box.SIMPLE_HEAVY)
        summary.add_column("Metric", style="bold yellow")
        summary.add_column("Count", justify="right", style="bold white")

        stats = {
            "Failed annotations": len(report.errors),
            "Successful annotations": len(report.successes),
        }

        for key, value in stats.items():
            summary.add_row(key, str(value))

        TyperUtils.console.print(Panel.fit(
            f"Start: [green]{report.start_time}[/green]\n"
            f"End:   [green]{report.end_time}[/green]",
            title="🕒 Timestamps",
            border_style="cyan"
        ))

        TyperUtils.console.print(summary)

        # --- Helper to render dict[subject, list[str]] as a table ---
        def format_dict_table(entries, color, title):
            """Formats up to 10 dict entries as a Rich table (Subject → Messages)."""
            if not entries:
                return None

            table = Table(title=title, box=box.MINIMAL_DOUBLE_HEAD, border_style=color)
            table.add_column("Subject", style=f"bold {color}", no_wrap=True)
            table.add_column("Messages", style=color)

            # Limit to first 10 subjects
            for i, (subject, messages) in enumerate(entries.items()):
                if i >= 10:
                    table.add_row("[bright_black]...and more[/bright_black]", "")
                    break
                # Limit each subject to first 3 messages for compactness
                msg_preview = "\n".join(messages[:3])
                if len(messages) > 3:
                    msg_preview += f"\n[bright_black]...and {len(messages) - 3} more[/bright_black]"
                table.add_row(subject, msg_preview)

            return table

        # --- Display first 10 errors ---
        error_table = format_dict_table(report.errors, "red", "❌ First Errors")
        if error_table:
            TyperUtils.console.print(error_table)

        # --- Display first 10 successes ---
        success_table = format_dict_table(report.successes, "green", "✅ First Successes")
        if success_table:
            TyperUtils.console.print(success_table)

        TyperUtils.console.rule()

    @staticmethod
    def save_yaml(report: UploadReport, filename: PosixPath = None):
        """Guarda el informe en un archivo YAML."""
        if not filename:
            timestamp = report.start_time.replace(":", "-").replace("T", "_")
            filename = f"upload_report_{timestamp}.yaml"

        data = asdict(report)
        for k, v in data.items():
            if isinstance(v, (PosixPath, Path)):
                data[k] = str(v)
            elif isinstance(v, HttpUrl):
                data[k] = str(v)

        with open(filename, "w", encoding="utf-8") as f:
            yaml.safe_dump(data, f, sort_keys=False, allow_unicode=True)
            #yaml.safe_dump(asdict(report), f, sort_keys=False, allow_unicode=True)

    @staticmethod
    def load_yaml(filename: PosixPath):
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
