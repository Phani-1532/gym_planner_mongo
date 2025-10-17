import json
from bson import ObjectId
from datetime import date, datetime

class MongoJsonEncoder(json.JSONEncoder):
    """
    Custom JSON encoder to handle MongoDB's ObjectId and Python's date/datetime objects.
    """
    def default(self, o):
        if isinstance(o, (datetime, date)):
            return o.isoformat()
        if isinstance(o, ObjectId):
            return str(o)
        return super().default(o)

def dumps(data):
    """A wrapper for json.dumps with the custom encoder."""
    return json.dumps(data, cls=MongoJsonEncoder)