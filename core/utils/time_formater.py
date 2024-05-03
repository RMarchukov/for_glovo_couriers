from datetime import datetime
import re


def ts_to_timesec(timestamp: int):
    dt = datetime.utcfromtimestamp(timestamp / 1000)

    hours_in_seconds = dt.hour * 3600  
    minutes_in_seconds = dt.minute * 60  
    return hours_in_seconds + minutes_in_seconds  


def str_to_timesec(time: str):
    pattern = r"(\d{1,2})[.:](\d{1,2})-(\d{1,2})[.:](\d{1,2})"
    match = re.match(pattern, time)

    start_hour = int(match.group(1)) * 3600
    start_minute = int(match.group(2)) * 60
    end_hour = int(match.group(3)) * 3600
    end_minute = int(match.group(4)) * 60

    start_sec = start_hour + start_minute
    end_sec = end_hour + end_minute

    return start_sec, end_sec