
'''List AWS accounts'''
import os
import boto3

from aws_lambda_powertools.logging import Logger
from aws_lambda_powertools.utilities.typing import LambdaContext
from aws_lambda_powertools.utilities.data_classes import (
    event_source,
    EventBridgeEvent
)

LOGGER = Logger(utc=True)

SNS_CLIENT = boto3.client('sns')
SNS_TOPIC_ARN = os.environ.get('SNS_TOPIC_ARN', 'UNSET')



def _main(data) -> None:
    '''Main work of function'''
    # Transform data

    # Send data to destination

    return


@LOGGER.inject_lambda_context
@event_source(data_class=EventBridgeEvent)
def handler(event: EventBridgeEvent, context: LambdaContext) -> None:
    '''Event handler'''
    LOGGER.debug('Event', extra={"message_object": event})

    _main(event.detail)

    return
