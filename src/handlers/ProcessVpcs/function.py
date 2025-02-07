
'''Process VPCs'''
import os
import json
import requests
from typing import TYPE_CHECKING, List

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    SQSEvent
)
import boto3

from common.model.account import AccountTypeWithTags
from common.model.entity import Entity, EntityMeta, EntitySpec
from common.util.jwt import JwtAuth

if TYPE_CHECKING:
    from mypy_boto3_ec2 import EC2Client
    from mypy_boto3_ec2.type_defs import VpcTypeDef
    from mypy_boto3_sts.type_defs import CredentialsTypeDef
    from mypy_boto3_sqs.type_defs import SendMessageResultTypeDef

LOGGER = Logger(utc=True)

# AWS
STS_CLIENT = boto3.client('sts')
CROSS_ACCOUNT_IAM_ROLE_NAME = os.environ.get('CROSS_ACCOUNT_IAM_ROLE_NAME', '')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', 'MUST_SET_SQS_QUEUE_URL')

# Catalog
CATALOG_ENDPOINT = os.environ.get('CATALOG_ENDPOINT', 'MUST_SET_CATALOG_ENDPOINT')
CLIENT_ID = os.environ.get('CLIENT_ID', 'MUST_SET_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'MUST_SET_CLIENT_SECRET')
JWT = JwtAuth(CLIENT_ID, CLIENT_SECRET)


class GetSystemOwnerError(Exception):
    '''Get System Owner Error'''
    def __init__(self, system) -> None:
        super().__init__('Failed to get owner for system: {}'.format(system))


def _get_cross_account_credentials(
    account_id: str,
    role_name: str
) -> 'CredentialsTypeDef':
    '''Return the IAM role for cross-account access'''
    role_arn = 'arn:aws:iam::{}:role/{}'.format(account_id, role_name)
    try:
        response = STS_CLIENT.assume_role(
            RoleArn=role_arn,
            RoleSessionName='ProcessVpcsResourcecollector'
        )
    except Exception as e:
        LOGGER.exception(e)
        raise e

    return response['Credentials']


def _get_cross_account_ec2_client(
    account_id: str,
    role_name: str
) -> 'EC2Client':
    '''Return an EC2 client with cross-account access'''
    credentials = _get_cross_account_credentials(
        account_id,
        role_name
    )
    client = boto3.client(
        'ec2',
        aws_access_key_id=credentials['AccessKeyId'],
        aws_secret_access_key=credentials['SecretAccessKey'],
        aws_session_token=credentials['SessionToken']
    )

    return client


def _send_queue_message(entity: Entity) -> 'SendMessageResultTypeDef':
    '''Send message to SQS'''
    sqs = boto3.client('sqs')
    r = sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(entity)
    )
    return r


def _create_vpc_entity(
    vpc: 'VpcTypeDef',
    account_id: str,
    region: str,
    auth: JwtAuth
) -> Entity:
    '''Create an entity for a VPC'''
    entity_type = 'ec2-vpc'
    tags = { tag.get('key'): tag.get('value', 'NO_VALUE') for tag in vpc.get('Tags', []) }
    system = tags.get('org:system', 'UNKNOWN')
    owner = _get_system_owner(system, auth)

    vpc_id = vpc.get('VpcId', '')

    entity_spec = EntitySpec({
        'system': system,
        'owner': owner,
        'type': entity_type,
        'lifecycle': vpc.get('State', 'UNKNOWN')
    })

    # FIXME: The odds of a resource collision are low enough at our scale that we'll just use
    # the default namespace. eventually we should figure out how to handle this.
    entity_meta = EntityMeta({
        'namespace': 'default',
        'name': '{}-{}'.format(entity_type, vpc_id),
        'title': vpc_id,
        'description': 'VPC {} in account {}'.format(vpc_id, account_id),
        'annotations': {
            "io.serverlessops/cloud-provider": "aws",
            'aws.amazon.com/arn': 'arn:aws:ec2:{}:{}:vpc/{}'.format(region, account_id, vpc_id),
            'aws.amazon.com/account-id': account_id,
            'aws.amazon.com/owner-account-id': vpc.get('OwnerId', 'UNKNOWN'),
            'aws.amazon.com/region': region,
            'aws.amazon.com/cidr-block': vpc.get('CidrBlock', 'UNKNOWN')
        }
    })
    entity = Entity({
        'apiVersion': 'backstage.io/v1alpha1',
        'kind': 'Resource',
        'metadata': entity_meta,
        'spec': entity_spec
    })
    return entity


def _get_system_owner(system: str, auth: JwtAuth) -> str:
    '''Return system owner'''
    r = requests.get(
        '/'.join([
            CATALOG_ENDPOINT,
            'default',
            'system',
            system
        ]),
        auth=auth
    )

    if not r.ok:
        LOGGER.error('Failed to get system owner', extra={'response': r.text})
        raise GetSystemOwnerError(system)

    return r.json().get('spec', {}).get('owner', 'UNKNOWN')


def _main(account_info: AccountTypeWithTags) -> None:
    '''Publish VPC to catalog.'''
    account_id = account_info.get('Id', '')
    ec2_client = _get_cross_account_ec2_client(
        account_id,
        CROSS_ACCOUNT_IAM_ROLE_NAME
    )

    region = ec2_client.meta.region_name

    vpcs = ec2_client.describe_vpcs()
    for vpc in vpcs['Vpcs']:
        entity = _create_vpc_entity(vpc, account_id, region, JWT)
        _send_queue_message(entity)



@LOGGER.inject_lambda_context
@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, _: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event._data})
    for record in event.records:
        account_info = AccountTypeWithTags(**json.loads(record.body))
        _main(account_info)

    return
