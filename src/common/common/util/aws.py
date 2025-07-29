from typing import TYPE_CHECKING

from aws_lambda_powertools.logging import Logger
from boto3 import Session
from botocore.client import BaseClient

if TYPE_CHECKING:
    from mypy_boto3_sts.type_defs import CredentialsTypeDef

LOGGER = Logger(utc=True)

def get_cross_account_credentials(
    account_id: str,
    role_name: str,
    session_name: str
) -> 'CredentialsTypeDef':
    '''Return the IAM credentials for cross-account access'''
    role_arn = 'arn:aws:iam::{}:role/{}'.format(account_id, role_name)
    try:
        sts_client = Session().client('sts')
        response = sts_client.assume_role(
            RoleArn=role_arn,
            RoleSessionName=session_name
        )
    except Exception as e:
        LOGGER.exception(e)
        raise e

    return response['Credentials']


def get_cross_account_client(
    service_name: str,
    account_id: str,
    role_name: str,
    session_name: str
) -> 'BaseClient':
    '''Return an AWS client client with cross-account access'''
    credentials = get_cross_account_credentials(
        account_id,
        role_name,
        session_name
    )

    session = Session(
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )

    # NOTE: client()'s argument takes a Literal value and I don't feel like defining all the
    # AWS services here so we just ignore the type check
    client = session.client(service_name)   # type: ignore

    return client