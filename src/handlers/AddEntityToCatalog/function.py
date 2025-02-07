
'''Add Entity to catalog'''
import os
import json
import requests

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    SQSEvent
)

from common.model.entity import Entity
from common.util.jwt import JwtAuth

LOGGER = Logger(utc=True)

CATALOG_ENDPOINT = os.environ.get('CATALOG_ENDPOINT', 'MUST_SET_CATALOG_ENDPOINT')

CLIENT_ID = os.environ.get('CLIENT_ID', 'MUST_SET_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'MUST_SET_CLIENT_SECRET')
JWT = JwtAuth(CLIENT_ID, CLIENT_SECRET)

class AddEntityToCatalogError(Exception):
    '''Add Account to Catalog Error'''
    def __init__(self, account_id) -> None:
        super().__init__('Failed to add account to catalog: {}'.format(account_id))


def _add_entity_to_catalog(entity: Entity, auth: JwtAuth) -> requests.Response:
    '''Add entity to catalog'''
    r = requests.put(
        '/'.join([
            CATALOG_ENDPOINT,
            entity['metadata']['namespace'],
            entity['kind'].lower(),
            entity['metadata']['name']
        ]),
        headers={
            'Content-Type': 'application/json'
        },
        json=entity,
        auth=auth
    )

    if not r.ok:
        LOGGER.error('Failed to add entity to catalog', extra={'response': r.text})
        raise AddEntityToCatalogError(entity['metadata']['title'])

    return r


def _main(entity: Entity) -> None:
    '''Publish account to catalog.'''
    _add_entity_to_catalog(entity, JWT)


@LOGGER.inject_lambda_context
@event_source(data_class=SQSEvent)
def handler(event: SQSEvent, _: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event._data})
    for record in event.records:
        entity = Entity(**json.loads(record.body))
        _main(entity)

    return
