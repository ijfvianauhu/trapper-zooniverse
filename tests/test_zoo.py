import filecmp
import logging
import os
import shutil
import tempfile
from pathlib import Path

from trapper_zooniverse.ZooniverseClient import ZooniverseClient
import pytest
import time

def test_zooniverse_client_connect(zooniverse_client:ZooniverseClient):
    try:
        zooniverse_client.connect()
        #collections = trapper_client.collections.get_all()
        #_validate_collections(collections)
        #TrapperClient.export_list_to_csv(collections, "/tmp/collections_all.csv")
        logging.info(f"Connected to Zooniverse as {zooniverse_client.username}")
    except Exception as e:
        logging.debug(f"Error fetching collections: {e}")
        assert False, f"Exception occurred: {e}"

def test_zooniverse_client_subset_sets_get_all(zooniverse_client:ZooniverseClient):
    try:
        x=zooniverse_client.subjectsets.get_all()
        logging.info(x)
        #collections = trapper_client.collections.get_all()
        #_validate_collections(collections)
        logging.info(x[0].__dict__)

        #TrapperClient.export_list_to_csv(collections, "/tmp/collections_all.csv")
        logging.debug(f"Connected to Zooniverse as {zooniverse_client.username}")
    except Exception as e:
        logging.debug(f"Error fetching collections: {e}")
        assert False, f"Exception occurred: {e}"

def test_zooniverse_client_subjectsets_get_by_id(zooniverse_client, existing_subjectset_id):
    try:
        ss = zooniverse_client.subjectsets.get_by_id(existing_subjectset_id)
        logging.debug(ss)
        assert int(ss.id) == existing_subjectset_id
    except Exception as e:
        logging.debug(f"Error fetching subject set by id: {e}")
        assert False, f"Exception occurred: {e}"

def test_zooniverse_client_subjectset_create_and_delete(zooniverse_client):
    tmp_name = f"pytest_subjectset_{int(time.time())}"

    try:
        ss_created = zooniverse_client.subjectsets.create(tmp_name)
        logging.info(f"Creado subjectset: {ss_created}")
        assert ss_created.display_name == tmp_name
        assert ss_created.id is not None

        # 2. Verificar que existe usando get_by_id
        ss_fetched = zooniverse_client.subjectsets.get_by_id(ss_created.id)
        logging.info(f"Recuperado subjectset: {ss_fetched}")
        assert ss_fetched.id == ss_created.id

        # 3. Eliminarlo
        deletion_result = zooniverse_client.subjectsets.delete(ss_created.id)
        logging.info(f"Resultado eliminación: {deletion_result}")

        # delete() puede devolver True o un objeto — comprobamos que no haya error
        assert deletion_result is not False

        # 4. Comprobar que ya no existe
        with pytest.raises(Exception):
            zooniverse_client.subjectsets.get_by_id(ss_created.id)

    except Exception as e:
        logging.error(f"Error en create/delete subjectset: {e}")
        assert False, f"Exception occurred: {e}"

def test_zooniverse_client_subsets_get_all(zooniverse_client:ZooniverseClient):
    """
     Test que obtiene todos los subjects de todos los subject sets
     del proyecto y comprueba que devuelve objetos de tipo Subject.
     """
    try:
        # Obtener todos los subject sets
        subject_sets = zooniverse_client.subjectsets.get_all()
        assert subject_sets, "No se encontraron subject sets en el proyecto"

        total_subjects = 0
        for ss in subject_sets:
            subjects = zooniverse_client.subjects.get_by_subjectset(ss.id)
            logging.info(f"SubjectSet {ss.display_name} ({ss.id}) tiene {len(subjects)} subjects")
            total_subjects += len(subjects)
            # Comprobación mínima: cada subject debe tener un id
            for sub in subjects:
                assert hasattr(sub, "id")

        logging.info(f"Total de subjects en el proyecto: {total_subjects}")
        assert total_subjects >= 0  # Siempre debe devolver un número válido

    except Exception as e:
        logging.error(f"Error consultando subjects: {e}")
        assert False, f"Exception occurred: {e}"

def test_zooniverse_client_subsets_create(zooniverse_client:ZooniverseClient):
    import tempfile
    from PIL import Image

    tmp_ss_name = f"pytest_subjectset_{int(time.time())}"
    subject_set = zooniverse_client.subjectsets.create(tmp_ss_name)
    assert subject_set.id is not None
    logging.info(f"Created SubjectSet {subject_set.display_name} (ID: {subject_set.id})")

    tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_file_path = tmp_file.name
    tmp_file.close()

    img = Image.new("RGB", (100, 100), color=(0, 0, 0))
    img.save(tmp_file_path)
    logging.info(f"Created temporary image at {tmp_file_path}")

    try:
        metadata = {"camera": "pytest_camera"}
        subject = zooniverse_client.subjects.create(tmp_file_path, subject_set, metadata)
        assert subject is not None
        logging.info(f"Created Subject with ID {subject.id} and metadata {subject.metadata}")
    finally:
        deletion_result = zooniverse_client.subjectsets.delete(subject_set.id)
        assert deletion_result is True
        logging.info(f"Deleted SubjectSet {subject_set.id}")

        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            logging.info(f"Deleted temporary file {tmp_file_path}")

def test_zooniverse_client_subsets_create_download(zooniverse_client:ZooniverseClient):
    """
    Test que:
      1. Crea un SubjectSet
      2. Sube un subject (imagen)
      3. Descarga la imagen del subject
      4. Comprueba que el archivo descargado es igual al original
      5. Borra todo
    """

    import tempfile
    from PIL import Image

    # --- 1️⃣ Crear SubjectSet temporal ---
    tmp_subjectset_name = f"pytest_subjectset_{int(time.time())}"
    subject_set = zooniverse_client.subjectsets.create(tmp_subjectset_name)
    assert subject_set.id is not None
    logging.info(f"Created SubjectSet {subject_set.display_name} (ID: {subject_set.id})")

    # --- 2️⃣ Crear imagen dummy local ---
    tmp_file = tempfile.NamedTemporaryFile(suffix=".png", delete=False)
    tmp_file_path = tmp_file.name
    tmp_file.close()

    img = Image.new("RGB", (100, 100), color=(123, 45, 67))  # color aleatorio
    img.save(tmp_file_path)
    logging.info(f"Created temporary image at {tmp_file_path}")
    downloaded_path = None
    try:
        metadata = {"camera": "pytest_camera"}
        subject = zooniverse_client.subjects.create(tmp_file_path, subject_set, metadata)
        assert subject is not None
        logging.info(f"Created Subject with ID {subject.id}")

        downloaded_path = zooniverse_client.subjects.download(subject.id)
        logging.info(f"Downloaded subject image to {downloaded_path}")
        assert os.path.exists(downloaded_path)

        are_equal = filecmp.cmp(tmp_file_path, downloaded_path, shallow=False)
        assert are_equal, "El archivo descargado NO coincide con el original"
        logging.info("Downloaded image is identical to the uploaded image.")

    finally:
        deletion_result = zooniverse_client.subjectsets.delete(subject_set.id)
        assert deletion_result is True
        logging.info(f"Deleted SubjectSet {subject_set.id}")

        if os.path.exists(tmp_file_path):
            os.remove(tmp_file_path)
            logging.info(f"Deleted temporary file {tmp_file_path}")

        if downloaded_path and os.path.exists(downloaded_path):
            os.remove(downloaded_path)
            logging.info(f"Deleted downloaded file {downloaded_path}")

def test_zooniverse_client__download_bulk_max_subjectset(zooniverse_client):
    """
    Test que descarga todos los subjects de un SubjectSet.
    Selecciona el SubjectSet con más subjects y descarga todas sus imágenes.
    """
    subject_sets = zooniverse_client.subjectsets.get_all()
    assert subject_sets, "No se encontraron SubjectSets en el proyecto."

    max_ss = None
    max_count = -1
    for ss in subject_sets:
        num_subjects = len(list(ss.subjects))
        logging.info(f"SubjectSet {ss.display_name} tiene {num_subjects} subjects.")
        if num_subjects > max_count:
            max_count = num_subjects
            max_ss = ss

    assert max_ss is not None, "No se pudo seleccionar un SubjectSet con subjects."
    logging.info(f"Seleccionado SubjectSet {max_ss.display_name} con {max_count} subjects.")

    temp_dir = tempfile.mkdtemp(prefix="bulk_download_")

    try:
        downloaded_files = zooniverse_client.subjectsets.download(max_ss.id, output_folder=Path(temp_dir))
        logging.info(f"Descargados {len(downloaded_files)} archivos. en {temp_dir}")

        assert len(downloaded_files) == max_count, "No se descargaron todos los subjects."

        for f in downloaded_files:
            assert os.path.exists(f), f"Archivo {f} no existe."

        from PIL import Image

        for f in downloaded_files:
            try:
                with Image.open(f) as img:
                    img.verify()  # Verifica que el archivo es una imagen válida
            except Exception:
                assert False, f"{f} no es una imagen válida o está corrupta"
    finally:
        # --- 7️⃣ Limpiar carpeta temporal ---
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
            logging.info(f"Carpeta temporal {temp_dir} eliminada.")
        pass