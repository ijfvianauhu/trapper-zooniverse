import logging
from typing import List, Any

from panoptes_client.workflow import Workflow
from trapper_client.TrapperClient import TrapperClient

from trapper_zooniverse.ZooniverseClient import ZooniverseClient

logger = logging.getLogger(__name__)

def check_trapper_connection(trapper_client: TrapperClient):
    """
    Verifies the connection to the Trapper API using the provided credentials.

    :param base_url: Base URL of the Trapper API.
    :type base_url: str
    :param user_name: Username or email used for authentication.
    :type user_name: str
    :param user_password: User password for authentication.
    :type user_password: str
    :param access_token: Optional API access token (can be ``None``).
    :type access_token: str
    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        trapper_client.classification_projects.get_all()
    except Exception as e:
        msg = f"Failed to connect to Trapper API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def check_zooniverse_connection(zooniverse_client: ZooniverseClient):
    """
    Verifies the connection to the Zooniverse API using the provided credentials.

    :param api_url: Base URL of the Zooniverse API.
    :type api_url: str
    :param user_name: Username or email used for authentication.
    :type user_name: str
    :param user_password: User password for authentication.
    :type user_password: str
    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        zooniverse_client.connect()
    except Exception as e:
        msg = f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def zooniverse_get_workflows(zooniverse_client:ZooniverseClient, id:int=None) -> List[Workflow]:
    """
    Verifies the connection to the Zooniverse API using the provided credentials.
    :param zooniverse_client: ZooniverseClient instance.
    :type  zooniverse_client: ZooniverseClient
    :param id: Optional workflow ID to fetch a specific workflow.
    :type id: int
    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        zooniverse_client.connect()

        if id is not None:
            ok = zooniverse_client.workflows.get_by_id(id)
        else:
            ok = zooniverse_client.workflows.get_all()
        return ok
    except Exception as e:
        msg = f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)


def zooniverse_get_subject_sets(zooniverse_client:ZooniverseClient, id = None, with_exports:bool=False,
                                wf_id=None) -> Any:
    """
    Verifies the connection to the Zooniverse API using the provided credentials.

    :param api_url: Base URL of the Zooniverse API.
    :type api_url: str
    :param user_name: Username or email used for authentication.
    :type user_name: str
    :param user_password: User password for authentication.
    :type user_password: str
    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        if id is not None:
            ss = zooniverse_client.subjects.get_by_id(id)
        elif wf_id:
            ss = zooniverse_client.subjectsets.get_subject_sets_from_workflow(wf_id)
        else:
            if with_exports:
                ss=zooniverse_client.subjectsets.with_exports()
            else:
                ss=zooniverse_client.subjectsets.get_all()
        return ss

    except Exception as e:
        msg = f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def zooniverse_get_subjects(zooniverse_client:ZooniverseClient, id = None, ss_id=None):
    """
    Verifies the connection to the Zooniverse API using the provided credentials.

    :param zooniverse_client: ZooniverseClient instance.
    :type  zooniverse_client: ZooniverseClient
    :param id: Optional subject ID to fetch a specific subject.
    :type id: int
    :param ss_id: Optional subject set ID to fetch subjects from a specific subject set.
    :type ss_id: int
    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        if id is None and ss_id is not None:
            s = zooniverse_client.subjects.get_by_subject_set(ss_id)
            s=zooniverse_client.subjects.get_by_subjectset
        s = zooniverse_client.subjects.get_by_id(id)

        return s

    except Exception as e:
        msg = f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def trapper_collections(trapper_client: TrapperClient):
    """
    Verifies the connection to the Trapper API using the provided credentials.

    :param base_url: Base URL of the Trapper API.
    :type base_url: str
    :param user_name: Username or email used for authentication.
    :type user_name: str
    :param user_password: User password for authentication.
    :type user_password: str
    :param access_token: Optional API access token (can be ``None``).
    :type access_token: str
    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        return trapper_client.collections.get_all()
    except Exception as e:
        msg = f"Failed to connect to Trapper API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def trapper_deployments(trapper_client:TrapperClient):
    """
    Verifies the connection to the Trapper API using the provided credentials.

    :raises Exception: If the connection fails or authentication is invalid.
    :return: None
    :rtype: None
    """
    try:
        return trapper_client.deployments.get_all()
    except Exception as e:
        msg = f"Failed to connect to Trapper API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)