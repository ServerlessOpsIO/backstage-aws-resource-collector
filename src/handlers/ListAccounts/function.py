
'''List AWS accounts'''
import os
import boto3
import json
from typing import TYPE_CHECKING, List, Optional

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    EventBridgeEvent
)

if TYPE_CHECKING:
    from mypy_boto3_sns.type_defs import PublishResponseTypeDef

from common.model.account import AccountType, AccountTypeWithTags
from common.util import JSONDateTimeEncoder

LOGGER = Logger(utc=True)

ORG_CLIENT = boto3.client('organizations')
SNS_CLIENT = boto3.client('sns')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'UNSET')


def _get_account_tags(accounts: List[AccountType]) -> List[AccountTypeWithTags]:
    '''Get tags for accounts'''
    accounts_with_tags = []
    for account in accounts:
        tags = ORG_CLIENT.list_tags_for_resource(
            # Haven't seen a situation where Id is not present
            ResourceId=account.get('Id', '')
        ).get('Tags')
        account_with_tags = {**account, 'Tags': tags}
        accounts_with_tags.append(account_with_tags)
    return accounts_with_tags


def _list_all_accounts(NextToken: Optional[str] = None) -> List[AccountType]:
    '''List AWS accounts'''
    accounts = []
    while True:
        response = ORG_CLIENT.list_accounts(
            **{ 'NextToken': NextToken } if NextToken else {}
        )
        if 'Accounts' in response:
            accounts += response['Accounts']

        if 'NextToken' in response:
            next_page = _list_all_accounts(NextToken=response['NextToken'])
            response['Accounts'] += next_page
        else:
            break
    return accounts


def _publish_accounts(accounts: List[AccountTypeWithTags]) -> List['PublishResponseTypeDef']:
    '''Publish account to SNS'''
    responses = []
    for account in accounts:
        LOGGER.debug('Publishing {}'.format(account.get('Id')), extra={"message_object": account})
        response = SNS_CLIENT.publish(
            TopicArn = SNS_TOPIC_ARN,
            Subject = 'AWS Account',
            Message = json.dumps(account, cls=JSONDateTimeEncoder)
        )
        LOGGER.debug('SNS Response for {}'.format(account.get('Id')), extra={"message_object": response})
        responses.append(response)
    return responses


def _main() -> None:
    '''List AWS accounts and publish to SNS'''
    accounts = _list_all_accounts()
    accounts_with_tags = _get_account_tags(accounts)
    _publish_accounts(accounts_with_tags)


@LOGGER.inject_lambda_context
@event_source(data_class=EventBridgeEvent)
def handler(event: EventBridgeEvent, context: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event})

    _main()

    return
