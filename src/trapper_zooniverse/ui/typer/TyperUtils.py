import json
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path
from typing import Union, List, Optional, Dict, Any, Callable
from rich.table import Table
from rich.console import Console
from rich.prompt import Prompt
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn, BarColumn, ProgressColumn, TaskID, \
    TimeRemainingColumn
from rich.panel import Panel
from rich.text import Text
from rich import box
import logging
import typer
from pydantic import BaseModel
import yaml

from trapper_zooniverse.i18n import _
from trapper_zooniverse.reports import Report
from trapper_zooniverse.ui.typer.settings import Settings

class TyperUtils:
    console = Console()
    logger = logging.getLogger(__name__)
    home = os.path.expanduser("~")

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
        TyperUtils.logger.error(message, exc_info=True)

    @staticmethod
    def fatal(message: str):
        TyperUtils.console.print(f"[red]:skull:[/red] {message}")
        TyperUtils.logger.critical(message, exc_info=True)
        raise typer.Exit(code=1)

    @staticmethod
    def success(message: str):
        TyperUtils.console.print(f"[green]:white_check_mark:[/green] {message}")
        TyperUtils.logger.info(message)

    @staticmethod
    def debug(message: str):
        if TyperUtils.logger.isEnabledFor(logging.DEBUG):
            TyperUtils.console.print(f"🐞 {message}")
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
    def display_config_table(config: Settings, title: str = "Config") -> None:
        """
        Muestra una tabla con los campos del modelo Pydantic.
        :param config:
        :param title:
        :return:
        """
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
                row.append(str(item.pk))
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
        """
        Prints the list of objects as a formatted JSON string.
        :param objects:
        :return:
        """
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

    #
    # Report methods
    #

    @staticmethod
    def get_default_report_dir():
        return Path(TyperUtils.home) / ("reports")

    @staticmethod
    def report_save(report, file_name=None):
        results_dir = TyperUtils.get_default_report_dir()
        results_dir.mkdir(parents=True, exist_ok=True)
        if file_name is None:
            unique_id = uuid.uuid4().hex[:8]
            file_name = f"report_{unique_id}_{datetime.now():%Y%m%d_%H%M%S}.yaml"
        report_file = results_dir / file_name
        report.to_yaml(report_file)
        return report_file

    @staticmethod
    def reports_in_directory(results_dir: Path):
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
    def report_display(report: "Report", raw: bool = False) -> None:
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

    # python
    def progress_bar2(
        func,
        func_args: tuple,
        func_kwargs: dict = None,
        title: str = "Processing",
        total=0,
        use_subtasks=False,
        custom_callback: callable = None,
    ) -> Any:
        """
        Display a Rich progress bar while executing a background function and processing
        events sent via a callback through an internal queue.

        Task ids may contain \":\" to indicate hierarchy (parent:child[:subchild...]).
        Recognized event statuses: 'start', 'progress', 'end', 'fail' (aliases: 'stop','finished').
        - 'progress' increases the task that generated it by 'step' (default 1).
        - 'end' / 'fail' are applied to the parent task if one exists; otherwise to the task itself.
        """
        from queue import Queue, Empty

        report: Report = None
        event_queue = Queue()

        def build_callback(status, task_id, name, total, step):
            event_queue.put((status, task_id, name, total, step))

        # envolver custom_callback si se proporciona (como antes)
        if custom_callback:

            def user_callback(*args, **kwargs):
                try:
                    TyperUtils.debug(f"Calling cutom_callback {args}...")
                    result = custom_callback(*args, **kwargs)
                    if result is None:
                        return
                    # Si devuelve iterable, encolar cada evento; si es único, encolarlo
                    if isinstance(result, (list, tuple)):
                        try:
                            event_queue.put(result, timeout=1)
                        except Exception as e:
                            TyperUtils.error(f"Failed to enqueue event from custom_callback: {e}")
                    else:
                        TyperUtils.error(f"Event from custom_callback must be list or tuple")
                except Exception as e:
                    TyperUtils.error(f"custom_callback raised an exception: {e}")

            callback = user_callback
        else:
            callback = build_callback

        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
            #console=TyperUtils.console,
        ) as progress:
            main_task = progress.add_task(
                f"[cyan]{title}...", total=total if (isinstance(total, int) and total > 0) else None
            )
            # mapping: full_task_id -> {"task_id": rich_task_id, "total": int|None, "completed": int, "description": str}
            tasks: Dict[str, Dict[str, Any]] = {}

            meta = {
                "task_id": main_task,
                "parent_id": None,
                "total": total,
                "completed": 0,
                "description": title,
            }

            tasks["__main__"] = meta

            def ensure_task(full_id: str, parent_id:str = None, description: Optional[str] = None, total_val: Optional[int] = None):
                """
                Create a rich task for full_id if not exists. Returns meta dict.
                """
                if full_id is None or full_id.strip() == "":
                    full_id = "__main__"

                TyperUtils.debug(f"Ensure task {full_id}")

                if full_id in tasks:
                    meta = tasks[full_id]
                    # actualizar metadata si se proporciona
                    if total_val is not None and total_val != meta["total"]:
                        progress.update(meta["task_id"], total=total_val)
                        meta["total"] = total_val
                    if description and description != meta["description"]:
                        progress.update(meta["task_id"], description=f"[cyan]{description}")
                        meta["description"] = description
                    return meta

                #if parent_id is not None and parent_id not in tasks:
                    # asegurar existencia del padre (sin total si no se da)
                #    ensure_task(parent_id, "__main__", description=parent_id, total_val=None)

                rich_parent = tasks["parent_id"]["task_id"] if parent_id in tasks else main_task
                task_total = total_val if (isinstance(total_val, int) and total_val > 0) else None
                desc = description or full_id
                rich_id = progress.add_task(f"[cyan]{desc}", total=task_total, visible = (use_subtasks == True))
                meta = {"task_id": rich_id, "parent_id": rich_parent,  "total": task_total, "completed": 0, "description": desc}
                tasks[full_id] = meta
                TyperUtils.debug(f"Created progress task for '{full_id}' (total={task_total})")
                return meta

            if func_kwargs is None:
                func_kwargs = {}
            final_args = func_args + (callback,)

            from concurrent.futures import ThreadPoolExecutor

            with ThreadPoolExecutor(max_workers=1) as executor:
                future = executor.submit(func, *final_args, **func_kwargs)
                while True:
                    try:
                        TyperUtils.debug("Trying get events...")
                        status, task_id, name, c_total, step = event_queue.get(timeout=0.1)
                        step = int(step) if step is not None else 1
                    except Empty:
                        TyperUtils.debug("Queue empty")
                        if future.done() and (total is None or total == 0) and event_queue.empty():
                            TyperUtils.debug("Exiting loop because future is done and queue is empty")
                            break
                        continue

                    # Normalizar strings
                    status = str(status).lower() if status is not None else ""
                    task_id = str(task_id) if task_id is not None else ""

                    name = name or task_id
                    MAX_LEN = 70
                    if len(name) > MAX_LEN:
                        name = name[: MAX_LEN - 3] + "..."

                    # determinar padre (si existe)
                    parts = task_id.split(":") if task_id else []
                    parent_id = ":".join(parts[:-1]) if len(parts) > 1 else None

                    TyperUtils.debug(f"Processing event {status} for '{task_id}' (parent='{parent_id}')")

                    # START: crear/actualizar la tarea origen y asegurarse del padre
                    if status == "start":
                        # crear tarea origen
                        description =  f"🟡  {name} {task_id}" if not parent_id else f"  🟡  {name} {task_id}"
                        ensure_task(task_id, parent_id, description=description, total_val=c_total)
                        # si tiene padre, asegurar también la existencia del padre (sin total si no se da)
                        #if parent_id:
                        #    ensure_task(parent_id, description=parent_id, total_val=None)
                        progress.log(description)

                    # PROGRESS: incrementar la tarea que generó el progress
                    elif status == "progress":
                        meta = ensure_task(task_id, description=name, total_val=c_total)
                        advance_by = step if step and step > 0 else 1
                        meta["completed"] += advance_by
                        progress.advance(meta["task_id"], advance_by)
                        #progress.log(f"→ {name} +{advance_by}")
                        # si alcanza total, marcar completado
                        if meta["total"] is not None and meta["completed"] >= meta["total"]:
                            progress.update(meta["task_id"], completed=meta["total"])
                            TyperUtils.success(f"Task '{task_id}' completed by progress")

                    # END / FAIL / STOP / FINISHED: aplicar a padre si existe, sino a la tarea misma
                    elif status in ("end", "fail", "stop", "finished"):

                        target_id = parent_id if parent_id else task_id
                        if not target_id:
                            TyperUtils.debug("Event without task id - ignoring")
                            continue

                        if status == "end" or status == "finished":
                            description = f"🟢  {name} {task_id} " if target_id == task_id else f"🟢  {target_id} ← {name}"
                        else:
                            description = f"🔴  {name} {task_id}" if target_id == task_id else f"🔴  {target_id} ← {name}"

                        # avanzar 1 unidad en la tarea objetivo
                        meta = ensure_task(target_id, description=description, total_val=None)
                        meta["completed"] += 1
                        progress.advance(meta["task_id"], 1)
                        # log visual
                        progress.log(description)

                        # si la tarea objetivo tiene total conocido y llegó al tope, actualizarla
                        if meta["total"] is not None and meta["completed"] >= meta["total"]:
                            progress.update(meta["task_id"], completed=meta["total"])
                            TyperUtils.debug(f"Marked '{target_id}' as fully completed ({meta['total']})")

                        # avanzar la barra principal también (unidad lógica completada)
                        try:
                            progress.advance(main_task, 1)
                        except Exception:
                            TyperUtils.debug("Failed to advance main_task")

                    else:
                        # estado desconocido -> log
                        # progress.log(f"{task_id}: {status} {name}")
                        pass

                    # Si conocemos total general y hemos alcanzado, terminar.
                    if isinstance(total, int) and total > 0:
                        # contar completados agregando completados de tareas top-level (sin padres)
                        top_completed = sum(m["completed"] for k, m in tasks.items() if ":" not in k)
                        TyperUtils.debug(f"Checking totals: top_completed={top_completed} / total={total}")
                        if top_completed >= total:
                            TyperUtils.debug("Reached overall total -> breaking")
                            # actualizar main_task al total exacto
                            progress.update(main_task, completed=total)
                            break

                # limpiar eventos restantes rápidamente
                while not event_queue.empty():
                    try:
                        _ = event_queue.get_nowait()
                    except Empty:
                        break

                try:
                    report = future.result(timeout=None)
                except Exception as exc:
                    TyperUtils.fatal(f"Error executing {title}: {exc}")

        return report

    @staticmethod
    def progress_bar(func,  func_args: tuple, func_kwargs: dict = None, title: str = "Processing", total=0,
                     use_subtasks=False, custom_callback:callable=None) -> Report:
        """
        Display a Rich progress bar while executing a background function and processing
        events sent via a callback through an internal queue.

        :param func: Callable executed in the background. It must accept positional arguments
                     from ``func_args`` and then receive a ``callback`` with signature
                     ``callback(status, subject_id, name)`` and the integer ``max_workers``
                     if the implementation requires it.
        :type func: Callable

        :param func_args: Tuple of positional arguments to pass to ``func`` before appending
                          the ``callback`` and ``max_workers``.
        :type func_args: tuple

        :param func_kwargs: Optional dictionary of keyword arguments to pass to ``func``.
        :type func_kwargs: dict | None

        :param title: Description text shown for the task in the progress bar.
        :type title: str

        :param total: Expected total number of items. Use ``None`` or ``0`` when unknown to
                      operate in indeterminate mode (the bar advances according to received events).
        :type total: int | None

        :returns: The ``Report`` instance returned by ``func`` when execution completes successfully,
                  or ``None`` if the background task failed or returned nothing.
        :rtype: Report | None

        :raises typer.Exit: On critical failures the function calls ``TyperUtils.fatal`` which
                            raises ``typer.Exit`` with a non-zero exit code.
        :raises Exception: Exceptions raised by ``func`` may be propagated or converted into
                           a fatal error.

        .. note::
           The provided ``callback`` must enqueue tuples of the form ``(status, subject_id, name)``
           into the internal ``Queue`` that the progress loop consumes. Recognized status values:

           - ``'start'`` — item processing started.
           - ``'end'``   — item processed successfully (increments progress).
           - ``'fail'``  — item processing failed.

        .. rubric:: Internal behaviour
           The function creates an internal :class:`queue.Queue` and runs ``func`` inside a
           :class:`concurrent.futures.ThreadPoolExecutor`. The main thread consumes queue events,
           updates :class:`rich.progress.Progress`, logs messages via :class:`TyperUtils` and, after
           the queue has been drained and the background future completes, returns the background
           ``Report`` (obtained via ``future.result()``).
        """

        from queue import Queue, Empty

        report: Report = None
        event_queue = Queue()

        def build_callback(status, task_id, name, total, step):
            event_queue.put((status, task_id, name, total, step))


        if custom_callback:
            def user_callback(*args, **kwargs):
                try:
                    # Llamar al callback del usuario
                    TyperUtils.debug(f"Calling callback {args}...")
                    result = custom_callback(*args, **kwargs)

                    # Si devuelve None, no hay eventos que encolar
                    if result is None:
                        return

                    # Si devuelve una iterable (lista/tupla), encolar cada evento
                    if isinstance(result, (list, tuple)):
                        try:
                            TyperUtils.debug(f"Encolando varios {result}...")
                            event_queue.put(result, timeout=1)
                        except Exception as e:
                            TyperUtils.error(f"Failed to enqueue event from custom_callback: {e}")
                    else:
                        TyperUtils.error(f"Failed to enqueue event from custom_callback: list or tuple expected")

                except Exception as e:
                    TyperUtils.error(f"custom_callback raised an exception: {e}")

            callback = user_callback
        else:
            callback = build_callback


        with Progress(
            "[progress.description]{task.description}",
            BarColumn(),
            "[progress.percentage]{task.percentage:>3.0f}%",
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            transient=False,
        ) as progress:
            task = progress.add_task(_(f"[cyan]{title}..."), total=total)
            subtasks = {}

            TyperUtils.debug("Preparing thread pool for collecting events...")
            with ThreadPoolExecutor(max_workers=1) as executor:
                TyperUtils.debug("Submitting thread for zooniverse_client.subjectsets.download...")
                if func_kwargs is None:
                    func_kwargs = {}
                final_args = func_args + (callback,)

                future = executor.submit(
                    func,
                    *final_args,
                    **func_kwargs,
                )

                completed = 0

                while True:
                    try:
                        TyperUtils.debug("Trying get events...")
                        status, task_id, name, c_total, step = event_queue.get(timeout=0.1)
                        #total = total if total and total > 0 else 1
                        step  = step if step and step > 0 else 1
                    except Empty:
                        TyperUtils.debug("Queue empty")
                        # si conocemos total, y future está done pero cola puede recibir más,
                        # no rompas solo porque queue.empty() sea True (condición de carrera).
                        if future.done() and total is None and event_queue.empty():
                            TyperUtils.debug("Exiting loop because future is done and queue is empty")
                            break
                        continue

                    TyperUtils.debug("Processing event {status}...")

                    if status == "start":
                        description = f"🟡  {name}"
                    elif status in ("end", "fail"):
                        description = f"🟢  {name}" if status == "end" else f"🔴  {name}"

                    MAX_LEN=70
                    if len(description) > MAX_LEN:
                        description = description[: MAX_LEN - 3] + "..."

                    if not use_subtasks:
                        if status == "start":
                            progress.log(description)
                        elif status in ("end", "fail"):
                            completed += 1
                            progress.advance(task, 1)
                            progress.log(description)
                    else:
                        if status == "start":
                            TyperUtils.debug(f"Add task for {task_id}")
                            stask = progress.add_task("  " + description, total=1)
                            subtasks[task_id] = stask
                        elif status in ("end", "fail"):
                            if task_id in subtasks:
                                TyperUtils.debug(f"Finish task for {task_id}")
                                stask = subtasks.pop(task_id)
                                progress.update(stask, completed=1, description="  "+ description)
                                completed += 1
                                progress.advance(task, 1)

                    # Si conocemos total, terminamos cuando hayamos recibido todos los eventos esperados.
                    if total is not None and completed >= total:
                        TyperUtils.debug(f"Completed all expected events {completed}/{total}.")
                        progress.update(task, completed=total)
                        TyperUtils.debug(f"Cleaning events queue...")
                        # consumir rápidamente cualquier resto (logs) sin bloquear demasiado
                        while not event_queue.empty():
                            try:
                                st = event_queue.get_nowait()
                                # opcional: procesar logs/errores adicionales si se necesita
                            except Empty:
                                break
                        break

                # Si no teníamos total y el future terminó, esperar a que la cola se vacíe definitivamente
                if total is None:
                    while not event_queue.empty():
                        try:
                            status, subject_id, name = event_queue.get_nowait()
                            if status == "end":
                                progress.advance(task, 1)
                            elif status == "fail":
                                progress.advance(task, 1)
                        except Empty:
                            break
                # Aquí se recupera siempre el resultado devuelto por la hebra
                try:
                    report = future.result(timeout=None)  # devuelve el Report o lanza excepción si falló
                except Exception as exc:
                    TyperUtils.fatal(_(f"Error executing {title}: {exc}"))

        return report


# python
def progress_bar_dynamic(func, func_args: tuple, func_kwargs: dict = None, title: str = "Processing",
                         max_workers: int = 4) -> Report:
    """
    Barra de progreso dinámica: crea/actualiza tareas cuando se reciben eventos.

    Eventos esperados (diccionario) - ejemplos:
      - Crear/actualizar tarea:
        {
          "type": "task",
          "task_name": "download_images",
          "description": "Downloading images",
          "total": 42,               # int | None
          "state": "started"         # started | finished | failed | updated
        }
      - Evento de ítem dentro de una tarea:
        {
          "type": "item",
          "task_name": "download_images",
          "item_name": "img_001.jpg",
          "item_state": "end",       # end | fail | start | message
          "item_message": "ok"       # texto opcional
        }

    El `func` debe aceptar los argumentos de `func_args` y recibir un `callback(event)` al final
    que encole los eventos descritos. La función ejecuta `func` en un ThreadPoolExecutor,
    consume la cola, crea tareas dinámicamente y devuelve el `Report` devuelto por `func`.
    """

    from queue import Queue, Empty
    from concurrent.futures import ThreadPoolExecutor

    report: Report = None
    event_queue = Queue()

    def callback(event):
        try:
            if event_queue is None:
                TyperUtils.error("event_queue is None — events will be lost")
                return
            event_queue.put(event, timeout=1)
        except Exception as e:
            TyperUtils.error(f"Failed to enqueue event: {e}")

    # mappings: task_name -> {"task_id": TaskID, "total": int|None, "completed": int}
    tasks = {}

    # Progress columns: si una tarea tiene total None se mostrará sin porcentaje
    with Progress(
        "[progress.description]{task.description}",
        BarColumn(),
        "[progress.percentage]{task.percentage:>3.0f}%",
        TextColumn("{task.completed}/{task.total}"),
        TimeElapsedColumn(),
        TimeRemainingColumn(),
        transient=False,
        console=TyperUtils.console
    ) as progress:

        main_task = progress.add_task(_(f"[cyan]{title}..."), total=None)

        if func_kwargs is None:
            func_kwargs = {}
        final_args = func_args + (callback, max_workers)

        with ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(func, *final_args, **func_kwargs)

            while True:
                try:
                    event = event_queue.get(timeout=0.1)
                except Empty:
                    # terminar si el trabajo de fondo terminó y no hay eventos pendientes
                    if future.done() and event_queue.empty():
                        TyperUtils.debug("Future done and queue empty -> breaking event loop")
                        break
                    continue

                # Normalizar evento (acepta dict o tupla)
                if isinstance(event, dict):
                    ev = event
                elif isinstance(event, (list, tuple)):
                    # permitir tuplas estilo: ("task", task_name, description, total, state)
                    try:
                        if len(event) >= 1 and event[0] in ("task", "item"):
                            if event[0] == "task":
                                ev = {
                                    "type": "task",
                                    "task_name": event[1],
                                    "description": event[2] if len(event) > 2 else None,
                                    "total": event[3] if len(event) > 3 else None,
                                    "state": event[4] if len(event) > 4 else None
                                }
                            else:
                                ev = {
                                    "type": "item",
                                    "task_name": event[1],
                                    "item_name": event[2] if len(event) > 2 else None,
                                    "item_state": event[3] if len(event) > 3 else None,
                                    "item_message": event[4] if len(event) > 4 else None
                                }
                        else:
                            TyperUtils.debug(f"Ignoring unknown tuple event: {event}")
                            continue
                    except Exception:
                        TyperUtils.debug(f"Malformed tuple event: {event}")
                        continue
                else:
                    TyperUtils.debug(f"Ignoring unsupported event type: {type(event)}")
                    continue

                etype = ev.get("type")
                tname = ev.get("task_name")
                # Crear tarea si no existe
                if etype == "task":
                    desc = ev.get("description") or tname
                    total = ev.get("total")
                    state = ev.get("state")
                    if tname not in tasks:
                        task_total = total if (isinstance(total, int) and total > 0) else None
                        task_id = progress.add_task(f"[cyan]{desc}", total=task_total)
                        tasks[tname] = {"task_id": task_id, "total": task_total, "completed": 0, "description": desc}
                        TyperUtils.info(f"Created task '{tname}' (total={task_total})")
                    else:
                        # actualización de metadatos de tarea
                        meta = tasks[tname]
                        if total is not None and total != meta["total"]:
                            progress.update(meta["task_id"], total=total)
                            meta["total"] = total
                        if desc and desc != meta["description"]:
                            progress.update(meta["task_id"], description=f"[cyan]{desc}")
                            meta["description"] = desc

                    if state in ("finished", "done"):
                        meta = tasks.get(tname)
                        if meta and meta["total"] is not None:
                            # marcar completado por completo
                            progress.update(meta["task_id"], completed=meta["total"])
                        TyperUtils.success(f"Task '{tname}' finished")
                    elif state in ("failed", "error"):
                        TyperUtils.error(f"Task '{tname}' failed")

                elif etype == "item":
                    item_name = ev.get("item_name")
                    item_state = ev.get("item_state")
                    item_message = ev.get("item_message")
                    if tname not in tasks:
                        # crear tarea implícita sin total conocido
                        task_id = progress.add_task(f"[cyan]{tname}", total=None)
                        tasks[tname] = {"task_id": task_id, "total": None, "completed": 0, "description": tname}
                        TyperUtils.info(f"Implicitly created task '{tname}' (unknown total)")

                    meta = tasks[tname]
                    if item_state in ("end", "finished", "success"):
                        meta["completed"] += 1
                        progress.advance(meta["task_id"], 1)
                        progress.log(_(f"[green]✓ {tname}: {item_name} {item_message or ''}"))
                    elif item_state in ("fail", "error"):
                        meta["completed"] += 1
                        progress.advance(meta["task_id"], 1)
                        progress.log(_(f"[red]✗ {tname}: {item_name} {item_message or ''}"))
                    elif item_state in ("start",):
                        progress.log(_(f"[yellow]→ {tname}: starting {item_name}"))
                    else:
                        # mensaje genérico
                        progress.log(f"{tname}: {item_name} {item_message or ''}")

                else:
                    TyperUtils.debug(f"Unknown event type received: {etype}")

            # al salir del loop principal, procesar cualquier evento restante
            while not event_queue.empty():
                try:
                    ev = event_queue.get_nowait()
                    # reusar la lógica (simple) para avanzar cuenta de ítems
                    if isinstance(ev, dict) and ev.get("type") == "item":
                        tname = ev.get("task_name")
                        if tname in tasks and ev.get("item_state") in ("end", "finished", "success", "fail", "error"):
                            meta = tasks[tname]
                            meta["completed"] += 1
                            progress.advance(meta["task_id"], 1)
                except Empty:
                    break

            # recuperar resultado de la tarea de fondo
            try:
                report = future.result(timeout=None)
            except Exception as exc:
                TyperUtils.fatal(_(f"Error executing {title}: {exc}"))

    return report
