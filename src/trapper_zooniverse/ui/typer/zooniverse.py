from pathlib import Path
from typing import Literal

from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TimeElapsedColumn

from trapper_zooniverse.TrapperZooniverseConnector import TrapperZooniverseConnector
from trapper_zooniverse.reports import Report
from trapper_zooniverse.ui.typer.TyperUtils import TyperUtils


def upload_collection( tzc : TrapperZooniverseConnector,
        collection: int,
        cproject: int,
        subjectset_name: str,
        n_images_seq: int,
        max_interval: int,
        attempts: int,
        delay: int,
        max_attempts_per_subject: int,
        delay_seconds_per_subject: int,
) -> Report :

    TyperUtils.debug(f"Starting upload_collection with values:{locals().items()}")
    with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("{task.completed}/{task.total}"),
            TimeElapsedColumn(),
    ) as progress:

        # Registro dinámico de tareas
        task_registry = {}

        def get_or_create_task(task_name: str, total=None, description=None):
            """
            Crea la tarea si no existe. Si existe, la devuelve.
            """
            if task_name not in task_registry:
                desc = description or task_name.replace("_", " ").title()
                task_id = progress.add_task(desc, total=total)
                task_registry[task_name] = task_id
            return task_registry[task_name]

        def progress_callback(
                task_name: str,
                state: str,
                advance: int = 1,
                total: int | None = None,
                description: str | None = None,
                set_total: bool = False,
                item_name:str = None,
                item_status: Literal["start", "end", "fail"] | None = None,
        ):
            """
            Callback flexible que soporta:
            - tareas determinadas   (con total)
            - tareas indeterminadas (total=None)
            - cambio de total a posteriori
            - añadir descripciones personalizadas
            """
            task_id = get_or_create_task(task_name, total, description)

            if set_total and total is not None:
                progress.update(task_id, total=total)

            # --- Estados ---
            if state == "start":
                new_desc = f"🟢  {description or task_name.replace('_', ' ').title()}"
                progress.update(task_id, description=new_desc)

            elif state == "end":
                new_desc = f"✔️  {description or task_name.replace('_', ' ').title()}"
                progress.update(task_id, completed=progress.tasks[task_id].total or 1,
                                description=new_desc)
                progress.stop_task(task_id)

            elif state == "fail":
                new_desc = f"❌  {description or task_name.replace('_', ' ').title()}"
                progress.update(task_id, description=new_desc)
                progress.stop_task(task_id)
                return  # no seguir avanzando

            if item_name is not None:
                if item_status == "start":
                    progress.log(f"[yellow]→ Starting processing item {item_name}")
                elif item_status == "end":
                    progress.log(f"[green]✓ Finished processing item {item_name}")
                elif item_status == "fail":
                    progress.log(f"[red]✗ Failed processing {item_name}")

                progress.advance(task_id, advance)

        report = tzc.upload_collection(
            subjectset_name=subjectset_name,
            collection=collection,
            classification_project=cproject,
            uploaded_file=None,
            n_images_seq=n_images_seq,
            max_interval=max_interval,
            attempts=attempts,
            delay=delay,
            max_attempts_per_subject=max_attempts_per_subject,
            delay_seconds_per_subject=delay_seconds_per_subject,
            progress_callback=progress_callback
        )

    return report

def public_annotations(tzc : TrapperZooniverseConnector, cp_id:int, collection_id: int, subjectset_id: int
                       , wf_id: int, observations_file:Path = None):
    results = tzc.upload_annotations(
        subjectset_id,
        wf_id,
        collection_id,
        cp_id,
        observations_file,
        None,
        None
    )

    return results
