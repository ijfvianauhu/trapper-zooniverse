import logging
from trapper_client.TrapperClient import TrapperClient

from trapper_zooniverse.ZooniverseClient import ZooniverseClient

logger = logging.getLogger(__name__)

def check_trapper_connection(base_url:str, user_name:str, user_password: str, access_token: str):
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
        trapper_client = TrapperClient(
            base_url=base_url,
            user_name=user_name,
            user_password=user_password,
            access_token=access_token
        )

        trapper_client.classification_projects.get_all()
    except Exception as e:
        msg = f"Failed to connect to Trapper API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def check_zooniverse_connection(user_name:str, user_password: str, project_id:str):
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
        zooniverse_client=ZooniverseClient(
            project_id= project_id,
            username= user_name,
            password= user_password,
        )

        zooniverse_client.connect()

    except Exception as e:
        msg = f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)


def zooniverse_get_workflows(user_name:str, user_password: str, project_id:str, id = None):
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
        zooniverse_client=ZooniverseClient(
            project_id= project_id,
            username= user_name,
            password= user_password,
        )

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


def zooniverse_get_subject_sets(user_name:str, user_password: str, project_id:str, id = None, with_exports:bool=False,
                                wf_id=None):
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
        zooniverse_client=ZooniverseClient(
            project_id= project_id,
            username= user_name,
            password= user_password,
        )

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

def zooniverse_get_subjects(user_name:str, user_password: str, project_id:str, id = None, ss_id=None):
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
        zooniverse_client=ZooniverseClient(
            project_id= project_id,
            username= user_name,
            password= user_password,
        )

        if id is None and ss_id is not None:
            s = zooniverse_client.subjects.get_by_subject_set(ss_id)
            s=zooniverse_client.subjects.get_by_subjectset
        s = zooniverse_client.subjects.get_by_id(id)

        return s

    except Exception as e:
        msg = f"Failed to connect to Zooniverse API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def trapper_collections(base_url:str, user_name:str, user_password: str, access_token: str):
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
        trapper_client = TrapperClient(
            base_url=base_url,
            user_name=user_name,
            user_password=user_password,
            access_token=access_token
        )
        return trapper_client.collections.get_all()
    except Exception as e:
        msg = f"Failed to connect to Trapper API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

def trapper_deployments(base_url:str, user_name:str, user_password: str, access_token: str):
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
        trapper_client = TrapperClient(
            base_url=base_url,
            user_name=user_name,
            user_password=user_password,
            access_token=access_token
        )
        return trapper_client.deployments.get_all()
    except Exception as e:
        msg = f"Failed to connect to Trapper API. Check your settings: {str(e)}"
        logger.error(msg)
        raise Exception(msg)

