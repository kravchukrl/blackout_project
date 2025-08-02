import logging
import argparse
import datetime
import os
import json
date_day = datetime.datetime.now().astimezone(datetime.timezone.utc).strftime("%Y-%m-%d")  # Get current time in UTC

# log_format = '[%(asctime)s][%(levelname)s] %(name)s: %(message)s'
log_format = '[%(asctime)s][%(levelname)-5s] %(module)s:%(lineno)d - %(message)s'
formatter = logging.Formatter(log_format)
logging.root.setLevel(logging.INFO)  # Set the root logger level to DEBUG
logging.basicConfig(filename=f'./logs/{date_day}_log.txt', 
                    format=log_format, encoding='utf-8')
# create console handler and set level to debug
ch = logging.StreamHandler()
ch.setLevel(logging.DEBUG)
ch.setFormatter(formatter)
logger = logging.getLogger(__name__)  # Use __name__ to get the name of the current module
logger.addHandler(ch)
logger.setLevel(logging.DEBUG)

# def getLogger(module):
#   return logger

def getArgs(module):
    parser = argparse.ArgumentParser(module)
    parser.add_argument("device_id", help="unique ID of device", type=str,default="temp",nargs='?')
    parser.add_argument("pin", help="GPIO pin BCM number https://pinout.xyz/ ", type=int, default=4,nargs='?')
    parser.add_argument("mode", help="Mode dev, prod etc", type=str, default='dev',nargs='?')
    return parser.parse_args()


def write_item_to_buffer(mode, filename, dict):
    filepath  = f'./buffer/{mode}/{filename}'
    logger.debug(f"Writing to file: {filepath} with data: {dict}")
    directory = os.path.dirname(filepath)
    os.makedirs(directory, exist_ok=True)
    with open(filepath, 'w') as f:
        json.dump(dict,f)

def get_buffered_items(mode):
    directory = f'./buffer/{mode}'
    items = {}
    if os.path.exists(directory):
        for filename in os.listdir(directory):
            if filename.endswith(".json"):
                filepath = os.path.join(directory, filename)
                logger.debug(f"Reading file: {filepath}")
                with open(filepath, 'r') as f:
                    item = json.load(f)
                    items[filepath] = item
    logger.debug(f"Number of buffered items: {len(items)}")
    return items        

def remove_buffered_item(filename):
    try:
        os.remove(filename)
        logger.debug(f"Removed buffered file: {filename}")
    except Exception as e:
        logger.error(f"Error removing buffered file {filename}: {e}")
        raise