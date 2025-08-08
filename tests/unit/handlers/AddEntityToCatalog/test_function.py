'''Test AddEntityToCatalog'''
# pylint: disable=redefined-outer-name, protected-access, import-outside-toplevel, unused-argument
from time import time
from types import ModuleType
from typing import Any, Callable, Generator
import jsonschema

import pytest
from pytest_mock import MockerFixture
import requests_mock

from aws_lambda_powertools.utilities.typing import LambdaContext

from common.model.entity import Entity
from common.util.jwt import AUTH_ENDPOINT, JwtAuth


# Requests
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

    # We can also use requests_mocker within tests too if necessary
    with requests_mocker:
        requests_mocker.register_uri(
            requests_mock.ANY,
            requests_mock.ANY,
            status_code=200,
        )
        yield fn


class TestData:
    '''Data validation tests'''
    def test_validate_data(self, mock_event_data: dict[str, Any], mock_event_data_schema: dict[str, Any]):
        '''Test event against schema'''
        jsonschema.Draft7Validator(mock_event_data, mock_event_data_schema)

    def test_validate_event(self, mock_event: dict[str, Any], mock_event_schema: dict[str, Any]):
        '''Test event against schema'''
        jsonschema.Draft7Validator(mock_event, mock_event_schema)


class TestCode:
    '''Code tests'''
    def test_AddEntityToCatalogError(self, mock_fn: ModuleType):
        '''Test AddEntityToCatalogError class'''
        e = mock_fn.AddEntityToCatalogError('account_id')
        assert str(e) == 'Failed to add account to catalog: account_id'

    def test__add_entity_to_catalog(
        self,
        mock_fn: ModuleType,
        mock_event_data: Entity,
        mock_endpoint: str,
        mock_auth: JwtAuth,
        requests_mocker: requests_mock.Mocker,
    ):
        '''Test _add_entity_to_catalog function'''
        r = mock_fn._add_entity_to_catalog(mock_event_data, mock_auth)

        assert requests_mocker.called == True
        assert requests_mocker.call_count == 1
        assert r.ok == True
        assert r.request.method == 'PUT'
        assert r.request.url == '{}/{}/{}/{}'.format(
            mock_endpoint,
            mock_event_data['metadata']['namespace'],
            mock_event_data['kind'].lower(),
            mock_event_data['metadata']['name']
        )

    def test__add_entity_to_catalog_fails(
        self,
        mock_fn: ModuleType,
        mock_event_data: Entity,
        mock_auth: JwtAuth,
        requests_mocker: requests_mock.Mocker,
    ):
        '''Test _add_entity_to_catalog function fails'''
        requests_mocker.register_uri(
            requests_mock.PUT,
            requests_mock.ANY,
            status_code=403,
        )

        with pytest.raises(mock_fn.AddEntityToCatalogError):
            mock_fn._add_entity_to_catalog(mock_event_data, mock_auth)

    def test__main(
        self,
        mock_fn: ModuleType,
        mock_event_data: Entity,
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

        mock_fn._main(mock_event_data)

    def test_handler(
        self,
        lambda_function_name: str,
        mock_fn: ModuleType,
        mock_context: Callable[[str], LambdaContext],
        mock_event_data: Entity,
        mock_event: dict[str, Any],
        mocker: MockerFixture
    ):
        '''Test calling handler'''
        import json
        from aws_lambda_powertools.utilities.data_classes import SQSEvent

        # Call the function
        mocker.patch.object(
            mock_fn,
            'JwtAuth',
            client_id='clientId',
            client_secret='clientSecret',
            token='token'
        )

        mock_event_sqs = SQSEvent(mock_event)
        mock_event_sqs._data['Records'][0]['body'] = json.dumps(mock_event_data)
        mock_fn.handler(mock_event_sqs, mock_context(lambda_function_name))