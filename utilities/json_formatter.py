from datetime import datetime
def formatJson(dict, measurement):
    data = {"measurement": measurement}
    data['fields'] = dict
    data['time'] = int(datetime.now().timestamp()* 10**9)
    return data