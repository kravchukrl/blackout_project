#!/usr/bin/env python

import RPi.GPIO as GPIO           # Allows us to call our GPIO pins and names it just GPIO
from dynamo import * 
import datetime
from utils import logger, getArgs,write_item_to_buffer,get_buffered_items,remove_buffered_item

# Reading arguments  device_id, pin, mode
args = getArgs('check_pin')
device_id = args.device_id
pin = args.pin
mode = args.mode
# Get current time in UTC
ts= datetime.datetime.now().astimezone(datetime.timezone.utc)  

date_day_hour = ts.strftime("%Y-%m-%d-%H")
date_minute = ts.strftime("%M")
date_iso = ts.isoformat()

logger.info(f"Start Reading. Device ID: {device_id}, Pin: {pin}, Mode: {mode}, Date: {date_iso}")

# Read Pin Status
GPIO.setmode(GPIO.BCM) # Set's GPIO pins to BCM GPIO numbering
GPIO.setup(pin, GPIO.IN, pull_up_down=GPIO.PUD_DOWN)  # Set our input pin to be an input
is_on = GPIO.input(pin)   # read pin status: 0 - off, 1 - on

logger.info(f'GPIO status. Device ID: {device_id}, Pin: {pin}, Mode: {mode}, PIN {pin} = {is_on}')

#write to buffer
item={
        'pk': f'device#{device_id}#sensor#{pin}#date#{date_day_hour}',
        'sk': f'time#{date_minute}',
        'pk_status': f'device#{device_id}#sensor#{pin}#status#new',
        'ts': date_iso,
        'reading': is_on,
}

# Write to buffered file, this useful when no connection to DynamoDB
# It'll push the buffered data to DynamoDB when connection is restored
write_item_to_buffer(mode, date_iso+'.json', item)

# Write to DyndamoDB buffered items
table = get_minutes_table(mode)
items = get_buffered_items(mode)
for filename, item in items.items():
    logger.debug(f"Buffered item to put to the table {table.name}: {item}")
    table.put_item(Item=item)
    logger.info(f"Buffered item saved to DynamoDB table {table.name}")
    remove_buffered_item(filename)
# logger.debug(f"Item to put to the table {table.name}: {item}")
# table.put_item(Item=item)
# logger.info(f"Item saved to DynamoDB table {table.name}")

