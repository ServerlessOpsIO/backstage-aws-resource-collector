'''Test AddEntityToCatalog'''
import json
import jsonschema
import os
from time import time
from types import ModuleType
from typing import Generator

import pytest
from pytest_mock import MockerFixture
import requests_mock

from aws_lambda_powertools.utilities.data_classes import SQSEvent
from aws_lambda_powertools.utilities.typing import LambdaContext

from common.model.entity import Entity
from common.test.aws import create_lambda_function_context
from common.util.jwt import AUTH_ENDPOINT, JwtAuth

FN_NAME = 'AddEntityToCatalog'
DATA_DIR = './data'
FUNC_DATA_DIR = os.path.join(DATA_DIR, 'handlers', FN_NAME)
EVENT = os.path.join(FUNC_DATA_DIR, 'event.json')
EVENT_SCHEMA = os.path.join(FUNC_DATA_DIR, 'event.schema.json')
DATA = os.path.join(FUNC_DATA_DIR, 'data.json')
DATA_SCHEMA = os.path.join(FUNC_DATA_DIR, 'data.schema.json')

### Fixtures

# FIXME: Need to handle differences between powertools event classes and the Event class
# Event
@pytest.fixture()
def mock_data(e=DATA) -> Entity:
    '''Return event data object'''
    with open(e) as f:
        return Entity(**json.load(f))

@pytest.fixture()
def data_schema(schema=DATA_SCHEMA):
    '''Return an data schema'''
    with open(schema) as f:
        return json.load(f)

@pytest.fixture()
def mock_event(e=EVENT) -> SQSEvent:
    '''Return a function event'''
    with open(e) as f:
        return SQSEvent(json.load(f))

@pytest.fixture()
def event_schema(schema=EVENT_SCHEMA):
    '''Return an event schema'''
    with open(schema) as f:
        return json.load(f)

@pytest.fixture()
def requests_mocker() -> requests_mock.Mocker:
    '''Return a requests mock'''
    # NOTE: Use as a decerator with Python 3 appears broken so use fixture.
    # ref. https://github.com/pytest-dev/pytest/issues/2749
    return requests_mock.Mocker()

@pytest.fixture()
def mock_endpoint() -> str:
    '''Return a mock endpoint'''
    return 'https://api.example.com/catalog'

@pytest.fixture()
def mock_auth(
    mocker: MockerFixture,
    requests_mocker: requests_mock.Mocker,
) -> Generator[JwtAuth, None, None]:
    '''Yield a JWT Auth object'''
    requests_mocker.register_uri(
        requests_mock.POST,
        AUTH_ENDPOINT,
        status_code=200,
        json={'access_token': 'token'}
    )

    jwt = JwtAuth('clientId', 'clientSecret')
    mocker.patch.object(jwt, 'token', 'jwt-token')
    mocker.patch.object(jwt, 'expiration', int(time()) + 600)

    yield jwt


# Function
@pytest.fixture()
def mock_context(function_name=FN_NAME):
    '''context object'''
    return create_lambda_function_context(function_name)

@pytest.fixture()
def mock_fn(
    mock_endpoint: str,
    mock_auth: JwtAuth,
    requests_mocker: requests_mock.Mocker,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.AddEntityToCatalog.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.AddEntityToCatalog.function.JWT',
        mock_auth
    )

    mocker.patch(
        'src.handlers.AddEntityToCatalog.function.CATALOG_ENDPOINT',
        mock_endpoint
    )

    # We can also use requests_mocker within tests too if necxessary
    with requests_mocker:
        requests_mocker.register_uri(
            requests_mock.ANY,
            requests_mock.ANY,
            status_code=200,
        )
        yield fn


### Data validation tests
def test_validate_data(mock_data, data_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_data, data_schema)

def test_validate_event(mock_event, event_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_event._data, event_schema)


### Code Tests
def test_AddEntityToCatalogError(
    mock_data: Entity,
    mock_fn: ModuleType
    ):
    '''Test AddEntityToCatalogError class'''
    e = mock_fn.AddEntityToCatalogError(mock_data)
    assert str(e) == 'Failed to add entity to catalog: MockResource'

def test__add_entity_to_catalog(
    mock_fn: ModuleType,
    mock_data: Entity,
    mock_endpoint: str,
    mock_auth: JwtAuth,
    requests_mocker: requests_mock.Mocker,
):
    r = mock_fn._add_entity_to_catalog(mock_data, mock_auth)

    assert requests_mocker.called == True
    assert requests_mocker.call_count == 1
    assert r.ok == True
    assert r.request.method == 'PUT'
    assert r.request.url == '{}/{}/{}/{}'.format(
        mock_endpoint,
        mock_data['metadata']['namespace'],
        mock_data['kind'].lower(),
        mock_data['metadata']['name']
    )


def test__add_entity_to_catalog_fails(
    mock_fn: ModuleType,
    mock_data: Entity,
    mock_auth: JwtAuth,
    requests_mocker: requests_mock.Mocker,
):
    '''Test _add_account_to_catalog function'''
    requests_mocker.register_uri(
        requests_mock.PUT,
        requests_mock.ANY,
        status_code=403,
    )

    with pytest.raises(mock_fn.AddEntityToCatalogError):
        mock_fn._add_entity_to_catalog(mock_data, mock_auth)


def test__main(
    mock_fn: ModuleType,
    mock_data: Entity,
    mocker: MockerFixture
):
    '''Test _main function'''
    mocker.patch.object(
        mock_fn,
        'JwtAuth',
        client_id='clientId',
        client_secret='clientSecret',
        token='token'
    )

    mock_fn._main(mock_data)


def test_handler_with_sqs_event(
    mock_fn: ModuleType,
    mock_context: LambdaContext,
    mock_data: Entity,
    mock_event: SQSEvent,
    mocker: MockerFixture
):
    '''Test calling handler'''
    # Call the function
    mocker.patch.object(
        mock_fn,
        'JwtAuth',
        client_id='clientId',
        client_secret='clientSecret',
        token='token'
    )

    mock_event._data['Records'][0]['body'] = json.dumps(mock_data)
    mock_fn.handler(mock_event, mock_context)

def test_handler_with_lambda_destinations_sqs_event(
    mock_fn: ModuleType,
    mock_context: LambdaContext,
    mock_data: Entity,
    mock_event: SQSEvent,
    mocker: MockerFixture
):
    '''Test calling handler'''
    # Call the function
    mocker.patch.object(
        mock_fn,
        'JwtAuth',
        client_id='clientId',
        client_secret='clientSecret',
        token='token'
    )

    mock_event._data['Records'][0]['body'] = json.dumps({ "responsePayload": mock_data })
    mock_fn.handler(mock_event, mock_context)