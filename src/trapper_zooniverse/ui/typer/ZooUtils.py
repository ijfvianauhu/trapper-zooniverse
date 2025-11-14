import json
from pathlib import Path, PosixPath
from typing import Union, List, Optional, Dict, Any, Callable, Tuple

from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils

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


class ZooUtils:
    console = Console()
    logger = logging.getLogger(__name__)

    #
    # Workflows
    #

    @staticmethod
    def show_workflows(workflows, title: str = "Workflows"):
        """
        Display a list of Zooniverse Workflows in a table, showing ID, name, version, and number of subject sets.

        Parameters
        ----------
        workflows : List[Workflow]
            List of Workflow objects.
        title : str
            Title for the table.
        """
        if not workflows:
            TyperUtils.warning(f"[yellow]No workflows to display in '{title}'[/yellow]")
            return

        table = Table(title=title, show_lines=True)
        table.add_column("ID", style="cyan", justify="right")
        table.add_column("Name", style="green")
        table.add_column("Version", style="magenta")
        table.add_column("Status", style="magenta")
        table.add_column("Subject Sets", style="yellow", justify="right")
        table.add_column("Last Export", style="yellow", justify="right")


        for wf in workflows:
            # Intentamos contar los subject sets (puede ser lazy-loaded)
            try:
                subject_sets_count = len(list(wf.links.subject_sets))
                classifications = list(Classification.where(workflow_id=wf.id))
                classifications_count= len(classifications)

            except Exception as e:
                subject_sets_count = 0

            table.add_row(
                str(wf.id),
                wf.display_name or "—",
                str(wf.version) if wf.version else "—",
                str(wf.active),
                str(subject_sets_count),
                str("not implemented")
            )

        TyperUtils.console.print(table)
        TyperUtils.info(f"Total workflows: {len(workflows)}")

    @staticmethod
    def show_workflow(workflow,
                      show_raw: bool = False,
        max_choices_preview: int = 10,
        title: Optional[str] = None) -> None:

        """
            Muestra por pantalla un workflow de Zooniverse usando rich.

            Args:
                workflow: dict con la definición completa del workflow (JSON).
                show_raw: si True, muestra al final el JSON formateado.
                max_choices_preview: número máximo de opciones a mostrar por tarea (si hay muchas).
                title: título opcional para la cabecera.
            """

        if not isinstance(workflow, dict):
            try:
                workflow = workflow.raw  # atributo que contiene el JSON completo
            except AttributeError:
                raise TypeError("El objeto recibido no es un dict ni un Workflow válido con atributo .raw")

        root_title = title or f"Workflow: {workflow.get('display_name', workflow.get('id', 'unknown'))}"
        tree = Tree(f":clipboard: [bold blue]{root_title}[/]")

        # Metadatos principales
        meta_tbl = Table.grid(padding=(0, 1))
        meta_tbl.add_column(justify="right", style="bold")
        meta_tbl.add_column()
        meta_tbl.add_row("id", str(workflow.get("id", "")))
        meta_tbl.add_row("display_name", str(workflow.get("display_name", "")))
        meta_tbl.add_row("version", str(workflow.get("version", "")))
        meta_tbl.add_row("active", str(workflow.get("active", "")))
        if workflow.get("tasks"):
            meta_tbl.add_row("n_tasks", str(len(workflow["tasks"])))
        if workflow.get("retirement"):
            meta_tbl.add_row("retirement", "yes")

        meta_tbl.add_row("n_classifications", str(len(list(Classification.where(workflow_id=workflow)))))
        meta_tbl.add_row("n_subject_sets", str(len(list(workflow["links"]["subject_sets"]))))

        tree.add(Panel(meta_tbl, title="Metadatos", expand=False))

        # Descripción (si existe)
        description = workflow.get("description") or workflow.get("display_name")
        if description:
            tree.add(Panel(Markdown(str(description)), title="Descripción", expand=False))

        # Tareas (tasks)
        tasks = workflow.get("tasks", {})
        if tasks:
            tasks_branch = tree.add(f":gear: [bold]Tareas ({len(tasks)})[/]")
            # Ordenar por key para reproducibilidad
            for task_key in sorted(tasks.keys()):
                task = tasks[task_key]
                task_label = f"[bold]{task_key}[/] — {task.get('type', 'unknown')}: {task.get('question', '')}"
                tnode = tasks_branch.add(task_label)

                # Info table por tarea
                t_tbl = Table.grid()
                t_tbl.add_column(style="bold", width=16)
                t_tbl.add_column()
                t_tbl.add_row("type", str(task.get("type", "")))
                t_tbl.add_row("question", str(task.get("question", "")[:200]))
                if "required" in task:
                    t_tbl.add_row("required", str(task.get("required")))
                if "help" in task:
                    t_tbl.add_row("help", str(task.get("help", "")[:200]))
                tnode.add(Panel(t_tbl, expand=False))

                # Tipos con opciones (multiple choice / dropdown / radio / combo)
                if "answers" in task and isinstance(task["answers"], list):
                    a_table = Table(show_header=True, header_style="bold magenta")
                    a_table.add_column("idx", width=4, justify="right")
                    a_table.add_column("label")
                    a_table.add_column("value")
                    for i, ans in enumerate(task["answers"][:max_choices_preview], start=1):
                        label = ans.get("label") if isinstance(ans, dict) else str(ans)
                        value = ans.get("value") if isinstance(ans, dict) else ""
                        a_table.add_row(str(i), str(label), str(value))
                    if len(task["answers"]) > max_choices_preview:
                        a_table.add_row("…", f"(+{len(task['answers']) - max_choices_preview} more)", "")
                    tnode.add(Panel(a_table, title="Opciones", expand=False))

                # Choice maps for complex tasks (e.g., combo, drawing)
                if task.get("type") in ("dropdown", "multiple", "single", "combo", "drawing"):
                    # show any extra keys
                    extras = {k: v for k, v in task.items() if
                              k not in ("type", "question", "answers", "help", "required")}
                    if extras:
                        ex_json = json.dumps(extras, indent=2, ensure_ascii=False)
                        tnode.add(Panel(Syntax(ex_json, "json", theme="monokai", word_wrap=True), title="Extras",
                                        expand=False))
        # Retirement rules
        retirement = workflow.get("retirement")
        if retirement:
            ret_panel = Panel(Syntax(json.dumps(retirement, indent=2, ensure_ascii=False), "json"),
                              title="Retirement rules")
            tree.add(ret_panel)

        # Tutorial / grouping / version info in subject sets
        if workflow.get("subject_sets"):
            ss_branch = tree.add(f":framed_picture: Subject sets ({len(workflow['subject_sets'])})")
            for s in workflow["subject_sets"]:
                label = s.get("display_name", s.get("id", "unknown"))
                ss_branch.add(f"[bold]{label}[/] — id: {s.get('id', '')}")

        # Mostrar árbol
        TyperUtils.console.print(tree)

        # Raw JSON (opcional)
        if show_raw:
            raw = json.dumps(workflow, indent=2, ensure_ascii=False)
            TyperUtils.console.rule("[bold]Raw JSON")
            TyperUtils.console.print(Syntax(raw, "json", word_wrap=True))


    #
    # Subject Sets
    #


    @staticmethod
    def show_subject_sets(subject_sets: list[SubjectSet]):
        """Muestra una tabla con los SubjectSets de Zooniverse."""
        table = Table(title="Zooniverse Subject Sets", show_lines=True)

        # Define las columnshow_cas
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
        TyperUtils.info(f"Total: {len(subject_sets)}")

    @staticmethod
    def show_subject_set(subject_set: SubjectSet, title: str = "Subject Set Details"):
        """
        Display a single Zooniverse SubjectSet as a detailed "card".

        Parameters
        ----------
        subject_set : SubjectSet
            The SubjectSet object to display.
        title : str
            Title for the panel.
        """

        try:
            subjects_count = getattr(subject_set, "set_member_subjects_count", "—")
        except Exception:
            subjects_count = "Unknown"

        try:
            workflows_count = len(subject_set.raw.get("links")["workflows"])
        except Exception:
            workflows_count = "Unknown"

        table = Table(show_header=False, show_lines=True)
        table.add_row(_("ID"), str(subject_set.id))
        table.add_row(_("Name"), subject_set.display_name or "—")
        table.add_row(_("Created At"), str(subject_set.created_at))
        table.add_row(_("Updated At"), str(subject_set.updated_at))
        table.add_row(_("Number of Subjects"), str(subjects_count))
        table.add_row(_("Number of Workflows"), str(workflows_count))
        table.add_row(_("Description"), subject_set.raw.get("display_name") or "—")

        panel = Panel(table, title=title, expand=False, border_style="green")
        TyperUtils.console.print(panel)

    @staticmethod
    def show_subjects(subjects: List[Subject], title: str = "Subjects"):
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
        table.add_column("Classifications", style="magenta")

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

            # Clas
            cls = list(Classification.where(subject_ids=[subj.id]))
            # Añadir fila de cada subject
            table.add_row(str(subj.id), metadata_str, locations_str)

        # Añadir fila final con atributos disponibles
        #table.add_row(
        #    "[bold yellow]Available Keys[/bold yellow]",
        #    ", ".join(sorted(all_metadata_keys)) if all_metadata_keys else "—",
        #    ", ".join(sorted(all_location_keys)) if all_location_keys else "—",
        #)

        TyperUtils.console.print(table)
        TyperUtils.info(f"Total: {len(subjects)}")

    @staticmethod
    def show_subject(subject: Subject, title: str = "Subject Details"):
        """
        Display a single Zooniverse Subject as a detailed "card".

        Parameters
        ----------
        subject : Subject
            The Subject object to display.
        title : str
            Title for the panel.
        """
        console = Console()

        try:
            subject_sets_count = len(subject.links.subject_sets)
        except Exception as e:
            print(e)
            subject_sets_count = "Unknown"

        # Mostrar metadata de forma resumida
        metadata_str = ""
        if subject.metadata:
            for key, value in subject.metadata.items():
                metadata_str += f"{key}: {value}\n"
            metadata_str = metadata_str.strip()
        else:
            metadata_str = "—"

        # Ubicaciones (locations) del Subject
        locations_str = ""
        if subject.locations:
            for loc in subject.locations:
                # loc puede ser un dict con tipo y url
                if isinstance(loc, dict):
                    locations_str += f"{loc.get('image/png') or loc.get('image/jpeg') or str(loc)}\n"
                else:
                    locations_str += f"{str(loc)}\n"
            locations_str = locations_str.strip()
        else:
            locations_str = "—"

        table = Table(show_header=False, show_lines=True)
        table.add_row("ID", str(subject.id))
        table.add_row("Created At", str(subject.created_at))
        table.add_row("Updated At", str(subject.updated_at))
        table.add_row("Number of SubjectSets", str(subject_sets_count))
        table.add_row("Locations", locations_str)
        table.add_row("Metadata", metadata_str)

        panel = Panel(table, title=title, expand=False, border_style="blue")
        TyperUtils.console.print(panel)


    @staticmethod
    def show_annotations_table(annotations: List[Tuple[int, str]], title: str = "Annotations"):
        """
        Display a list of Zooniverse annotations in a table.

        Parameters
        ----------
        annotations : List[Tuple[int, str]]
            List of tuples (subject_set_id, export_url) returned by get_all().
        title : str
            Title for the table.
        """
        if not annotations:
            TyperUtils.warning(f"[yellow]No annotations to display in '{title}'[/yellow]")
            return

        table = Table(title=title, show_lines=True)
        table.add_column("SubjectSet ID", style="cyan", justify="right")
        table.add_column("Export Available", style="green", justify="center")
        table.add_column("Export URL", style="magenta")

        for subject_set_id, export_url in annotations:
            available = "✅" if export_url else "❌"
            url_display = str(export_url) if export_url else "—"
            # Si la URL es muy larga, se puede truncar
            if len(url_display) > 60:
                url_display = url_display[:57] + "..."
            table.add_row(str(subject_set_id), available, url_display)

        TyperUtils.console.print(table)
        TyperUtils.info(f"Total subject sets: {len(annotations)}")

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
