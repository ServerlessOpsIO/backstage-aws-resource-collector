import os
import sys
from collections import namedtuple
from typing import TYPE_CHECKING, cast, Callable

import pytest

if TYPE_CHECKING:
    from aws_lambda_powertools.utilities.typing import LambdaContext

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