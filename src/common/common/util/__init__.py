import datetime
from json import JSONEncoder

class JSONDateTimeEncoder(JSONEncoder):
    '''Encode JSON when datetime objects are present'''

    def default(self, obj):
        if isinstance(obj, (datetime.datetime, datetime.date)):
            return obj.isoformat()