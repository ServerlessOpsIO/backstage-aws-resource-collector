
'''Process ECS Clusters'''
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
    from mypy_boto3_ecs import ECSClient
    from mypy_boto3_ecs.type_defs import ClusterTypeDef, TagTypeDef
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
            RoleSessionName='ListEcsClustersResourcecollector'
        )
    except Exception as e:
        LOGGER.exception(e)
        raise e

    return response['Credentials']


def _get_cross_account_ecs_client(
    account_id: str,
    role_name: str
) -> 'ECSClient':
    '''Return an ECS client with cross-account access'''
    credentials = _get_cross_account_credentials(
        account_id,
        role_name
    )
    client = boto3.client(
        'ecs',
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


def _create_ecs_cluster_entity(
    cluster: 'ClusterTypeDef',
    cluster_tags: 'List[TagTypeDef]',
    auth: JwtAuth
) -> Entity:
    '''Create an entity for an ECS cluster'''
    # Type says key and value are not required which is interesting. Jumping through hoops to
    # make mypy happy
    tags = {tag.get('key'): tag.get('value', 'NO_VALUE') for tag in cluster_tags }
    system = tags.get('org:system', 'UNKNOWN')
    owner = _get_system_owner(system, auth)

    region, account_id = cluster.get('clusterArn', '').split(':')[3:5]
    entity_type = 'ecs-cluster'

    entity_spec = EntitySpec({
        'system': system,
        'owner': owner,
        'type': entity_type,
        'lifecycle': cluster.get('status', 'UNKNOWN')
    })

    entity_meta = EntityMeta({
        'namespace': account_id,
        'name': '{}-{}'.format(entity_type, cluster.get('clusterName', '')),
        'title': cluster.get('clusterName', ''),
        'description': 'ECS Cluster {} in account {}'.format(cluster.get('clusterName', ''), account_id),
        'annotations': {
            "io.serverlessops/cloud-provider": "aws",
            'aws.amazon.com/arn': cluster.get('clusterArn', ''),
            'aws.amazon.com/account-id': account_id,
            'aws.amazon.com/region': region,
            'aws.amazon.com/cluster-name': cluster.get('clusterName', ''),
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
    '''Publish account to catalog.'''
    ecs_client = _get_cross_account_ecs_client(
        account_info.get('Id', ''),
        CROSS_ACCOUNT_IAM_ROLE_NAME
    )

    clusters_list = ecs_client.list_clusters()
    clusters = ecs_client.describe_clusters(
        clusters=clusters_list['clusterArns']
    )

    for cluster in clusters['clusters']:
        # Type says ARN not requited. Guess there is some corner case where it may not exist.
        if cluster.get('clusterArn'):
            cluster_tags = ecs_client.list_tags_for_resource(
                #
                resourceArn=cluster.get('clusterArn', '')
            ).get('tags', [])
            entity = _create_ecs_cluster_entity(cluster, cluster_tags, JWT)
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
