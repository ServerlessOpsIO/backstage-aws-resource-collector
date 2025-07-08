
'''List AWS accounts'''
import os
import boto3
import json
from typing import TYPE_CHECKING, List, Optional, Sequence

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    EventBridgeEvent
)

if TYPE_CHECKING:
    from mypy_boto3_events.type_defs import PutEventsRequestEntryTypeDef, PutEventsResponseTypeDef


from common.model.account import AccountType, AccountTypeWithTags
from common.util import JSONDateTimeEncoder

LOGGER = Logger(utc=True)

ORG_CLIENT = boto3.client('organizations')
EVENTS_CLIENT = boto3.client('events')
EVENT_BUS_NAME = os.environ.get('EVENT_BUS_NAME', 'UNSET')


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
    LOGGER.debug('Accounts', extra={"message_object": accounts})
    return accounts


def _publish_accounts(accounts: List[AccountTypeWithTags]) -> 'PutEventsResponseTypeDef':
    '''Publish account to EventBridge'''
    account_entries: Sequence[PutEventsRequestEntryTypeDef] = [
        {
            'Source': 'self.ListAccounts',
            'DetailType': '',
            'Detail': json.dumps(account, cls=JSONDateTimeEncoder),
            'EventBusName': EVENT_BUS_NAME,
            'Resources': [
                account.get('Arn', '')
            ],
        } for account in accounts
    ]

    responses = EVENTS_CLIENT.put_events(
        Entries=account_entries
    )

    LOGGER.debug('EventBridge Response', extra={"message_object": responses})
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
