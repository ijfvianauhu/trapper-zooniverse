import os
import pytest
from trapper_zooniverse.ZooniverseClient import ZooniverseClient
from dotenv import load_dotenv
load_dotenv()

@pytest.fixture
def zooniverse_client():
    client = ZooniverseClient(
        project_id=os.getenv("ZOONIVERSE_PROJECT_ID"),
        username=os.getenv("ZOONIVERSE_USERNAME"),
        password=os.getenv("ZOONIVERSE_PASSWORD"),
    )
    client.connect()
    yield client
    client.disconnect()

@pytest.fixture
def existing_subjectset_name():
    return os.getenv("TEST_EXISTING_SUBJECTSET_NAME")

@pytest.fixture
def existing_subjectset_id():
    return int(os.getenv("TEST_EXISTING_SUBJECTSET_ID"))