import logging
import pytest
from dotenv import load_dotenv
from trapper_zooniverse.ZooniverseClient import ZooniverseClient
#from trapper_client.Schemas import TrapperCollection, TrapperCollectionCP, TrapperCollectionRP

#
#  pytest -o log_cli=true --log-cli-level=DEBUG
#

@pytest.fixture(scope="module")
def zooniverse_client():
    load_dotenv()
    client = ZooniverseClient.from_environment()
    #assert client.base_url.startswith("http")
    return client

"""
def _validate_collections(collections, expected_type=TrapperCollection):
    
    assert hasattr(collections, "results")
    assert hasattr(collections, "pagination")

    if collections.results:  # only if results is not empty
        assert isinstance(collections.results[0], expected_type)
"""

def test_zooniverse_client_connect(zooniverse_client):
    try:
        zooniverse_client.connect()
        #collections = trapper_client.collections.get_all()
        #_validate_collections(collections)
        #TrapperClient.export_list_to_csv(collections, "/tmp/collections_all.csv")
        logging.debug(f"Connected to Zooniverse as {zooniverse_client.username}")
    except Exception as e:
        logging.debug(f"Error fetching collections: {e}")
        assert False, f"Exception occurred: {e}"

def test_zooniverse_client_subset_sets_get_all(zooniverse_client):
    try:
        x=zooniverse_client.subset_sets_get_all()
        logging.debug(x)
        #collections = trapper_client.collections.get_all()
        #_validate_collections(collections)
        #TrapperClient.export_list_to_csv(collections, "/tmp/collections_all.csv")
        logging.debug(f"Connected to Zooniverse as {zooniverse_client.username}")
    except Exception as e:
        logging.debug(f"Error fetching collections: {e}")
        assert False, f"Exception occurred: {e}"
