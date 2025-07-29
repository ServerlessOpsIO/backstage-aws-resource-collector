from aws_lambda_powertools.utilities.data_classes.common import DictWrapper
from aws_lambda_powertools.utilities.data_classes import (
    EventBridgeEvent
)

class OrgAccountEventRequestParameters(DictWrapper):
    '''Request Parameters for account operations'''
    @property
    def account_id(self) -> str:
        '''Account name'''
        return self['accountId']


class OrgAccountEventDetail(DictWrapper):
    '''Event detail for account operation'''
    @property
    def aws_region(self) -> str:
        '''AWS region where the event originated'''
        return self['awsRegion']

    @property
    def recipient_account_id(self) -> str:
        '''Account ID of the recipient'''
        return self['recipientAccountId']

    @property
    def event_name(self) -> str:
        '''Name of the event operation'''
        return self['eventName']

    @property
    def request_parameters(self) -> OrgAccountEventRequestParameters:
        '''Request parameters'''
        return OrgAccountEventRequestParameters(self['requestParameters'])


class OrgAccountEvent(EventBridgeEvent):
    '''Event for Account operations'''
    @property
    def detail(self) -> OrgAccountEventDetail:
        '''Typed event detail for account operations'''
        return OrgAccountEventDetail(self['detail'])