'''Global fixtures for testing'''
# pylint: disable=redefined-outer-name, protected-access, import-outside-toplevel, unused-argument

import os
import sys
import json
from collections import namedtuple
from typing import TYPE_CHECKING, cast, Any, Callable

import pytest

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.typing import LambdaContext

DATA_DIR = './data'
EVENT_FILE_NAME = 'event.json'
EVENT_SCHEMA_FILE_NAME = 'event.schema.json'
EVENT_DATA_FILE_NAME = 'event-data.json'
EVENT_DATA_SCHEMA_FILE_NAME = 'event-data.schema.json'
OUTPUT_FILE_NAME = 'output.json'
OUTPUT_SCHEMA_FILE_NAME = 'output.schema.json'
RESPONSE_FILE_NAME = 'response.json'
RESPONSE_SCHEMA_FILE_NAME = 'response.schema.json'
RESPONSE_DATA_FILE_NAME = 'response-data.json'
RESPONSE_DATA_SCHEMA_FILE_NAME = 'response-data.schema.json'

# NOTE: Hack so we can test against local functions without installing them
# into the venv as pytest expects
#
# ref: https://github.com/pytest-dev/pytest/issues/2421#issuecomment-403724503
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

@pytest.fixture()
def lambda_function_name(request: pytest.FixtureRequest) -> str:
    '''Return the name of the Lambda function being tested'''
    return request.path.parent.name


@pytest.fixture()
def mock_context() -> Callable[[str], 'LambdaContext']:
    '''context object'''
    def _make_context(function_name: str) -> 'LambdaContext':
        context_info = {
            'aws_request_id': '00000000-0000-0000-0000-000000000000',
            'function_name': function_name,
            'function_version': '$LATEST',
            'invoked_function_arn': 'arn:aws:lambda:us-east-1:012345678910:function:{}'.format(function_name),
            'log_group_name': '/aws/lambda/{}'.format(function_name),
            'log_stream_name': '000/00/00/[$LATEST]00000000000000000000000000000000',
            'memory_limit_in_mb': 128,
            'identity': None,
            'tenant_id': None,
            'client_context': None,
            'get_remaining_time_in_millis': lambda: 0
        }

        Context = namedtuple('LambdaContext', context_info.keys())
        context = Context(*context_info.values())
        # FIXME: Would like a better way to match the namedtuple to the LambdaContext type
        return cast('LambdaContext', context)
    return _make_context


### Event
@pytest.fixture()
def mock_event_file_name(lambda_function_name) -> str | None:
    '''Return the event file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, EVENT_FILE_NAME)

@pytest.fixture()
def mock_event(mock_event_file_name) -> dict | None:
    '''Return event from a file'''
    if mock_event_file_name is not None and os.path.exists(mock_event_file_name):
        with open(mock_event_file_name) as f:
            event = json.load(f)
    else:
        event = None

    return event


@pytest.fixture()
def mock_event_schema_filename(lambda_function_name) -> str | None:
    '''Return the event schema file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, EVENT_SCHEMA_FILE_NAME)

@pytest.fixture()
def mock_event_schema(mock_event_schema_filename) -> dict | None:
    '''Return event schema from a file'''
    if mock_event_schema_filename is not None and os.path.exists(mock_event_schema_filename):
        with open(mock_event_schema_filename) as f:
            event_schema = json.load(f)
    else:
        event_schema = None

    return event_schema


### Event Data
@pytest.fixture()
def mock_event_data_filename(lambda_function_name) -> str | None:
    '''Return the event data file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, EVENT_DATA_FILE_NAME)

@pytest.fixture()
def mock_event_data(mock_event_data_filename) -> dict[str, Any] | None:
    '''Return event data from a file'''
    if mock_event_data_filename is not None and os.path.exists(mock_event_data_filename):
        with open(mock_event_data_filename) as f:
            event_data = json.load(f)
    else:
        event_data = None

    return event_data

@pytest.fixture()
def mock_event_data_schema_filename(lambda_function_name) -> str | None:
    '''Return the event data schema file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, EVENT_DATA_SCHEMA_FILE_NAME)

@pytest.fixture()
def mock_event_data_schema(mock_event_data_schema_filename) -> dict | None:
    '''Return event data schema from a file'''
    if mock_event_data_schema_filename is not None and os.path.exists(mock_event_data_schema_filename):
        with open(mock_event_data_schema_filename) as f:
            event_data_schema = json.load(f)
    else:
        event_data_schema = None

    return event_data_schema


### Output
@pytest.fixture()
def mock_output_file_name(lambda_function_name) -> str | None:
    '''Return the output file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, OUTPUT_FILE_NAME)

@pytest.fixture()
def mock_output(mock_output_file_name) -> dict[str, Any] | None:
    '''Return output from a file'''
    if mock_output_file_name is not None and os.path.exists(mock_output_file_name):
        with open(mock_output_file_name) as f:
            output = json.load(f)
    else:
        output = None

    return output

@pytest.fixture()
def mock_output_schema_filename(lambda_function_name) -> str | None:
    '''Return the output schema file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, OUTPUT_SCHEMA_FILE_NAME)

@pytest.fixture()
def mock_output_schema(mock_output_schema_filename) -> dict[str, Any] | None:
    '''Return output schema from a file'''
    if mock_output_schema_filename is not None and os.path.exists(mock_output_schema_filename):
        with open(mock_output_schema_filename) as f:
            output_schema = json.load(f)
    else:
        output_schema = None

    return output_schema


### Response
@pytest.fixture()
def mock_response_file_name(lambda_function_name) -> str | None:
    '''Return the response file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, RESPONSE_FILE_NAME)

@pytest.fixture()
def mock_response(mock_response_file_name) -> dict[str, Any] | None:
    '''Return response from a file'''
    if mock_response_file_name is not None and os.path.exists(mock_response_file_name):
        with open(mock_response_file_name) as f:
            response = json.load(f)
    else:
        response = None

    return response

@pytest.fixture()
def mock_response_schema_filename(lambda_function_name) -> str | None:
    '''Return the response schema file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, RESPONSE_SCHEMA_FILE_NAME)

@pytest.fixture()
def mock_response_schema(mock_response_schema_filename) -> dict | None:
    '''Return response schema from a file'''
    if mock_response_schema_filename is not None and os.path.exists(mock_response_schema_filename):
        with open(mock_response_schema_filename) as f:
            response_schema = json.load(f)
    else:
        response_schema = None

    return response_schema

@pytest.fixture()
def mock_response_data_filename(lambda_function_name) -> str | None:
    '''Return the response data file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, RESPONSE_DATA_FILE_NAME)

@pytest.fixture()
def mock_response_data(mock_response_data_filename) -> dict[str, Any] | None:
    '''Return response data from a file'''
    if mock_response_data_filename is not None and os.path.exists(mock_response_data_filename):
        with open(mock_response_data_filename) as f:
            response_data = json.load(f)
    else:
        response_data = None

    return response_data

@pytest.fixture()
def mock_response_data_schema_filename(lambda_function_name) -> str | None:
    '''Return the response data schema file name'''
    return os.path.join(DATA_DIR, 'handlers', lambda_function_name, RESPONSE_DATA_SCHEMA_FILE_NAME)

@pytest.fixture()
def mock_response_data_schema(mock_response_data_schema_filename) -> dict[str, Any] | None:
    '''Return response data schema from a file'''
    if mock_response_data_schema_filename is not None and os.path.exists(mock_response_data_schema_filename):
        with open(mock_response_data_schema_filename) as f:
            response_data_schema = json.load(f)
    else:
        response_data_schema = None

    return response_data_schema
