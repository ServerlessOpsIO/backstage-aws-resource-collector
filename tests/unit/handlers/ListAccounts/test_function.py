'''Test ListAccounts'''
from dataclasses import asdict
import json
import jsonschema
import os
from types import ModuleType
from typing import Generator, List

import pytest
from pytest_mock import MockerFixture


import boto3
from mypy_boto3_organizations import OrganizationsClient
from mypy_boto3_organizations.type_defs import AccountTypeDef, TagTypeDef
from mypy_boto3_sns import SNSClient
from moto import mock_aws

from aws_lambda_powertools.utilities.data_classes import EventBridgeEvent
from aws_lambda_powertools.utilities.typing import LambdaContext
from common.test.aws import create_lambda_function_context

FN_NAME = 'ListAccounts'
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
def mock_event(e=EVENT) -> EventBridgeEvent:
    '''Return a function event'''
    with open(e) as f:
        return EventBridgeEvent(json.load(f))

@pytest.fixture()
def event_schema(schema=EVENT_SCHEMA):
    '''Return an event schema'''
    with open(schema) as f:
        return json.load(f)
# AWS Clients
#
# NOTE: Mocking AWS services must also be done before importing the function.
@pytest.fixture()
def aws_credentials() -> None:
    '''Mocked AWS Credentials for moto.'''
    os.environ["AWS_ACCESS_KEY_ID"] = "testing"
    os.environ["AWS_SECRET_ACCESS_KEY"] = "testing"
    os.environ["AWS_SECURITY_TOKEN"] = "testing"
    os.environ["AWS_SESSION_TOKEN"] = "testing"
    os.environ["AWS_DEFAULT_REGION"] = "us-east-1"

@pytest.fixture()
def mocked_aws(aws_credentials):
    '''Mock all AWS interactions'''
    with mock_aws():
        yield

@pytest.fixture()
def mock_orgs_client(mocked_aws) -> Generator[OrganizationsClient, None, None]:
    orgs_client = boto3.client('organizations')
    yield orgs_client

@pytest.fixture()
def mock_sns_client(mocked_aws) -> Generator[SNSClient, None, None]:
    sns_client = boto3.client('sns')
    yield sns_client

@pytest.fixture()
def mock_sns_topic_arn(mock_sns_client) -> str:
    '''Create a mock resource'''
    mock_topic_name = 'MockTopic'
    r = mock_sns_client.create_topic(Name=mock_topic_name)
    return r.get('TopicArn')

@pytest.fixture()
def mock_organization(mock_orgs_client) -> None:
    '''Mock organization'''
    mock_orgs_client.create_organization()


@pytest.fixture()
def mock_account(
    mock_orgs_client: OrganizationsClient,
    mock_organization
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


# Function
@pytest.fixture()
def mock_context(function_name=FN_NAME):
    '''context object'''
    return create_lambda_function_context(function_name)

@pytest.fixture()
def mock_fn(
    mock_sns_topic_arn: str,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ListAccounts.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.ListAccounts.function.SNS_TOPIC_ARN',
        mock_sns_topic_arn
    )

    yield fn


### Data validation tests
# FIXME: Need to handle differences between powertools event classes and the Event class
def test_validate_event(mock_event, event_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_event._data, event_schema)


### Code Tests
def test__get_account_tags(
    mock_fn: ModuleType,
    mock_account: AccountTypeDef,
    mock_account_tags: List[TagTypeDef],
):
    '''Test _get_account_tags function'''
    account_with_tags = mock_fn._get_account_tags([mock_account])[0]
    assert 'Tags' in account_with_tags
    assert len(account_with_tags['Tags']) > 0
    assert account_with_tags['Tags'] == mock_account_tags


def test__list_all_accounts(
    mock_fn: ModuleType,
    mock_orgs_client: OrganizationsClient,
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
    mock_fn: ModuleType,
    mock_account: AccountTypeDef,
):
    '''Test _publish_accounts function'''
    account_with_tags = mock_fn._get_account_tags([mock_account])[0]
    response = mock_fn._publish_accounts([account_with_tags])
    assert len(response) > 0


def test__main(
    mock_fn: ModuleType,
):
    '''Test _main function'''
    mock_fn._main()


def test_handler(
    mock_fn: ModuleType,
    mock_context: LambdaContext,
    mock_event: EventBridgeEvent,
):
    '''Test calling handler'''
    # Call the function
    mock_fn.handler(mock_event, mock_context)