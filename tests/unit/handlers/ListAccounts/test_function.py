'''Test ListAccounts'''
from dataclasses import asdict
import json
import jsonschema
import os
from types import ModuleType
from typing import Generator

import pytest
from pytest_mock import MockerFixture


import boto3
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
def mock_sns_client(mocked_aws) -> Generator[SNSClient, None, None]:
    sns_client = boto3.client('sns')
    yield sns_client

@pytest.fixture()
def mock_sns_topic_name(mock_sns_client) -> str:
    '''Create a mock resource'''
    mock_topic_name = 'MockTopic'
    mock_sns_client.create_topic(Name=mock_topic_name)
    return mock_topic_name

# Function
@pytest.fixture()
def mock_context(function_name=FN_NAME):
    '''context object'''
    return create_lambda_function_context(function_name)

@pytest.fixture()
def mock_fn(
    mock_sns_topic_name: str,
    mocker: MockerFixture
) -> Generator[ModuleType, None, None]:
    '''Return mocked function'''
    import src.handlers.ListAccounts.function as fn

    # NOTE: use mocker to mock any top-level variables outside of the handler function.
    mocker.patch(
        'src.handlers.ListAccounts.function.SNS_TOPIC_ARN',
        mock_sns_topic_name
    )

    yield fn


### Data validation tests
# FIXME: Need to handle differences between powertools event classes and the Event class
def test_validate_event(mock_event, event_schema):
    '''Test event against schema'''
    jsonschema.Draft7Validator(mock_event._data, event_schema)


### Code Tests
def test__main(
    mock_fn: ModuleType,
    mock_data
):
    '''Test _main function'''
    mock_fn._main(mock_data)


def test_handler(
    mock_fn: ModuleType,
    mock_context,
    mock_event: EventBridgeEvent,
    mock_data
    mock_sns_client: SNSClient,
):
    '''Test calling handler'''
    # Call the function
    mock_fn.handler(mock_event, mock_context)