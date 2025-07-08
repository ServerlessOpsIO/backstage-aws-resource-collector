'''Test ListAccounts'''
# pylint: disable=redefined-outer-name, protected-access, import-outside-toplevel, unused-argument

from types import ModuleType
from typing import Callable, Any, Generator, List
import jsonschema

import pytest
from pytest_mock import MockerFixture

from mypy_boto3_organizations import OrganizationsClient
from mypy_boto3_organizations.type_defs import AccountTypeDef, TagTypeDef
from mypy_boto3_events import EventBridgeClient

from aws_lambda_powertools.utilities.typing import LambdaContext

### Fixtures
# AWS Clients
#
@pytest.fixture()

def mock_events_client(make_mocked_client: Callable) -> Generator[EventBridgeClient, None, None]:
    '''Mock EventBridge Client'''
    yield make_mocked_client('events')

@pytest.fixture()
def mock_event_bus_name(mock_events_client) -> str:
    '''Return the event bus name'''
    mock_event_bus_name = 'MockEventBus'
    r = mock_events_client.create_event_bus(Name=mock_event_bus_name)
    return mock_event_bus_name

@pytest.fixture()
def mock_orgs_client(make_mocked_client: Callable) -> Generator[OrganizationsClient, None, None]:
    '''Mock Organizations Client'''
    yield make_mocked_client('organizations')


@pytest.fixture()
def mock_organization(mock_orgs_client) -> None:
    '''Mock organization'''
    mock_orgs_client.create_organization()


@pytest.fixture()
def mock_account(
    mock_orgs_client: OrganizationsClient,
    mock_organization: None
) -> AccountTypeDef:
    '''Mock account'''
    account_config = {
        'Email': 'admin+mock-account@example.com',
        'AccountName': 'Mock Account',
        'Tags': [
            {
                "Key": "org:system",
                "Value": "mock_system"
            },
            {
                "Key": "org:domain",
                "Value": "mock_domain"
            },
            {
                "Key": "org:owner",
                "Value": "group:mock_group"
            }
        ]
    }

    response = mock_orgs_client.create_account(**account_config)
    account_id = response.get('CreateAccountStatus', {}).get('AccountId', '')
    return mock_orgs_client.describe_account(AccountId=account_id).get('Account')


@pytest.fixture()
def mock_account_tags(
    mock_orgs_client: OrganizationsClient,
    mock_account: AccountTypeDef,
) -> List[TagTypeDef]:
    '''Return account tags'''
    return mock_orgs_client.list_tags_for_resource(
        ResourceId=mock_account.get('Id', '')
    ).get('Tags', [])


@pytest.fixture()
def mock_fn(
    mock_event_bus_name: str,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ListAccounts.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.ListAccounts.function.EVENT_BUS_NAME',
        mock_event_bus_name
    )

    yield fn


class TestData:
    '''Data validation tests'''
    def test_validate_event(self, mock_event: dict[str, Any], mock_event_schema: dict[str, Any]):
        '''Test event against schema'''
        jsonschema.Draft7Validator(mock_event, mock_event_schema)


class TestCode:
    '''Code tests'''
    def test__get_account_tags(
        self,
        mock_fn: ModuleType,
        mock_account: AccountTypeDef,
        mock_account_tags: List[TagTypeDef],
    ):
        '''Test _get_account_tags function'''
        account_with_tags = mock_fn._get_account_tags([mock_account])[0]
        assert 'Tags' in account_with_tags
        assert len(account_with_tags['Tags']) > 0
        assert account_with_tags['Tags'] == mock_account_tags


    @pytest.mark.usefixtures("mock_organization")
    def test__list_all_accounts(
        self,
        mock_fn: ModuleType,
        mock_account: AccountTypeDef,
    ):
        '''Test _list_all_accounts function'''
        # Call the function
        accounts = mock_fn._list_all_accounts()
        account_ids = [account.get('Id', '') for account in accounts]

        # Assertions
        assert len(accounts) > 0
        assert mock_account.get('Id') in account_ids


    def test__publish_accounts(
        self,
        mock_fn: ModuleType,
        mock_account: AccountTypeDef,
    ):
        '''Test _publish_accounts function'''
        account_with_tags = mock_fn._get_account_tags([mock_account])[0]
        response = mock_fn._publish_accounts([account_with_tags])
        assert len(response) > 0


    @pytest.mark.usefixtures("mock_account")
    def test__main(
        self,
        mock_fn: ModuleType,
    ):
        '''Test _main function'''
        mock_fn._main()


    @pytest.mark.usefixtures("mock_account")
    def test_handler(
        self,
        lambda_function_name: str,
        mock_fn: ModuleType,
        mock_context: Callable[[str], LambdaContext],
        mock_event: dict,
    ):
        '''Test calling handler'''
        # Call the function
        mock_fn.handler(mock_event, mock_context(lambda_function_name))