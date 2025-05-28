
'''Remove Entity from catalog'''
import os
import requests

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
)

from common.model.entity import Entity
from common.util.jwt import JwtAuth

LOGGER = Logger(utc=True)

CATALOG_ENDPOINT = os.environ.get('CATALOG_ENDPOINT', 'MUST_SET_CATALOG_ENDPOINT')

CLIENT_ID = os.environ.get('CLIENT_ID', 'MUST_SET_CLIENT_ID')
CLIENT_SECRET = os.environ.get('CLIENT_SECRET', 'MUST_SET_CLIENT_SECRET')
JWT = JwtAuth(CLIENT_ID, CLIENT_SECRET)

class RemoveEntityFromCatalogError(Exception):
    '''Remove Entity From Catalog Error'''
    def __init__(self, entity: Entity) -> None:
        name = entity['metadata']['title']
        super().__init__('Failed to remove entity from catalog: {}'.format(name))

def _remove_entity_from_catalog(entity: Entity, auth: JwtAuth) -> requests.Response:
    '''Add entity to catalog'''
    r = requests.delete(
        '/'.join([
            CATALOG_ENDPOINT,
            entity['metadata']['namespace'],
            entity['kind'].lower(),
            entity['metadata']['name']
        ]),
        headers={
            'Content-Type': 'application/json'
        },
        auth=auth,
        timeout=10
    )

    if not r.ok:
        LOGGER.error('Failed to remove entity from catalog', extra={'response': r.text, 'entity': entity})
        raise RemoveEntityFromCatalogError(entity)

    return r


def _main(entity: Entity) -> requests.Response:
    '''Publish account to catalog.'''
    return _remove_entity_from_catalog(entity, JWT)


@LOGGER.inject_lambda_context
@event_source(data_class=Entity)
def handler(event: Entity, _: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event})

    return
