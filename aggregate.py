#!/usr/bin/env python

from dynamo import * 
from utils import *
# import argparse
import datetime
# import logging

# logging.basicConfig()
# logging.root.setLevel(logging.INFO)

# logger = getLogger('aggregate')
args = getArgs('aggregate')
device_id = args.device_id
pin = args.pin
mode = args.mode


# This function read from the minutes table and aggregate to  the hours table
#
# 'ts': aggregation  timestamp
# 'unknown": number of unknown reading during te hour 
# 'on': number of ON reading during te hour
# 'off': number of OFF reading during te hour
# 'expected': value of expected readings during the hour (1440 mins in an hour),
# 'count' : readins readings count (ON+OFF) 
def aggregateMinutesToHours(mode):
    logger.info(f"Aggregating minutes to hours {args}")

    table_name = f'{mode}-blackout-monitor-minutes'
    table = get_hours_table(mode)

    pk = query_first_pk_to_aggregate(table_name, device_id, pin)

    while pk is not None:
        items = query_data_by_pk(table_name, pk)
        expected_readings = 60
        readings_count = len(items)
        unknown_readings = expected_readings - readings_count
        on_readings = off_readings = 0
        for item in items:
            on_readings += int(item.get('reading', 0))
        off_readings = readings_count - on_readings
                  
        item={
            'pk': pk[:-3], #day, ie device#alex_rpi#sensor#4#date#2025-06-03
            'sk': f'time#{pk[-2:]}',#hour
            'pk_status': f'device#{device_id}#sensor#{pin}#status#new',
            'ts':datetime.datetime.now().astimezone(datetime.timezone.utc).isoformat(), # Get current time in UTC
            'unknown': unknown_readings,
            'on': on_readings,
            'off': off_readings,
            'expected': expected_readings,
            'count' : readings_count

        }
        logger.info(f"Items to aggregate: {len(items)} for pk {pk}, item: {item}")
        table.put_item(Item=item) 
        update_status_as_done(table_name, items)
        pk = query_first_pk_to_aggregate(table_name, device_id, pin)
    logger.info(f"Done. Aggregating minutes to hours {args}")
        # pk = None


# This function read from the hours table and aggregate to  the days table
# Fields are the same as in aggregateMinutesToHours
def aggregateHoursToDays(mode):
    logger.info(f"Aggregating hours to days {args}")

    table_name = f'{mode}-blackout-monitor-hours'
    table = get_days_table(mode)

    pk = query_first_pk_to_aggregate(table_name, device_id, pin)

    while pk is not None:
        # pk = query_pk_to_aggregate(table_name, device_id, sensorId)
        items = query_data_by_pk(table_name, pk)
        expected_readings = 24*60  # 24 hours in a day, each hour has 60 minutes
        readings_count = len(items)
        on_readings = off_readings = 0
        for item in items:
            on_readings += int(item.get('on', 0))
            off_readings += int(item.get('off', 0))
        unknown_readings = expected_readings - (on_readings + off_readings)          
        item={
            'pk': pk[:-3], #month, ie device#alex_rpi#sensor#4#date#2025-06
            'sk': f'time#{pk[-2:]}',#day
            'pk_status': f'device#{device_id}#sensor#{pin}#status#new',
            'ts':datetime.datetime.now().astimezone(datetime.timezone.utc).isoformat(), # Get current time in UTC
            'unknown': unknown_readings,
            'on': on_readings,
            'off': off_readings,
            'expected': expected_readings,
            'count' : readings_count

        }
        logger.info(f"Items to aggregate: {len(items)} for pk {pk}, item: {item}")
        table.put_item(Item=item) 
        update_status_as_done(table_name, items)
        pk = query_first_pk_to_aggregate(table_name, device_id, pin)
        # pk = None
    logger.info(f"Aggregating hours to days {args}")

aggregateMinutesToHours('dev')
aggregateHoursToDays('dev')