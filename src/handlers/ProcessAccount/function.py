'''process account entity'''
import os
import json
import requests
from typing import TYPE_CHECKING

import boto3
from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    SQSEvent
)

if TYPE_CHECKING:
    from mypy_boto3_sqs.type_defs import SendMessageResultTypeDef

from common.model.account import AccountTypeWithTags
from common.model.entity import Entity, EntityMeta, EntityMetaLinks, EntitySpec
from common.util.jwt import JwtAuth

LOGGER = Logger(utc=True)
SQS_CLIENT = boto3.client('sqs')
SQS_QUEUE_URL = os.environ.get('SQS_QUEUE_URL', 'MUST_SET_SQS_QUEUE_URL')

CATALOG_ENDPOINT = os.environ.get('CATALOG_ENDPOINT', 'MUST_SET_CATALOG_ENDPOINT')
CLIENT_ID = os.environ.get('CLIENT_ID', 'MUST_SET_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'MUST_SET_CLIENT_SECRET')
JWT = JwtAuth(CLIENT_ID, CLIENT_SECRET)


class GetSystemOwnerError(Exception):
    '''Get System Owner Error'''
    def __init__(self, system) -> None:
        super().__init__('Failed to get owner for system: {}'.format(system))


def _send_queue_message(entity: Entity) -> 'SendMessageResultTypeDef':
    '''Send message to SQS'''
    sqs = boto3.client('sqs')
    r = sqs.send_message(
        QueueUrl=SQS_QUEUE_URL,
        MessageBody=json.dumps(entity)
    )
    return r


def _get_entity_data(account_info: AccountTypeWithTags, auth: JwtAuth) -> Entity:
    '''Return entity data'''
    account_id = account_info.get('Id', '')

    account_tags = {tag['Key']: tag['Value'] for tag in account_info.get('Tags', [])}
    system = account_tags.get('org:system', 'UNKNOWN')
    owner = _get_system_owner(system, auth)

    entity_spec = EntitySpec({
        'owner': owner,
        'type': 'cloud-account',
        'system': system,
        'lifecycle': account_info.get('Status', '')
    })

    entity_links = EntityMetaLinks([
        {
            'url': 'https://serverlessops.awsapps.com',
            'title': 'AWS Console',
            'type': 'admin-console',
            'icon': 'aws',
        }
    ])

    entity_meta = EntityMeta({
        'namespace': 'default',
        'name': 'aws-{}'.format(account_id),
        'title': account_id,
        'description': account_info.get('Name', ''),
        'annotations': {
            "io.serverlessops/cloud-provider": "aws",
            'aws.amazon.com/account-id': account_id,
            'aws.amazon.com/account-email': account_info.get('Email', ''),
            'aws.amazon.com/arn': account_info.get('Arn', ''),
        },
        'links': entity_links
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
        LOGGER.error('Failed to get system owner', extra={'response': r.__dict__})
        raise GetSystemOwnerError(system)

    return r.json().get('spec', {}).get('owner', 'UNKNOWN')


def _main(account_info: AccountTypeWithTags) -> None:
    '''Publish account to catalog.'''
    entity = _get_entity_data(account_info, JWT)
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
