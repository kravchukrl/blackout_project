
import boto3
from  botocore.exceptions import ClientError
import logging
from boto3.dynamodb.conditions import Key
from utils import logger 
dynamodb = boto3.resource('dynamodb')



# Partition key:
#   device#<device_id>#sensor#<sensor_id>#date#<YYYY-MM-DD-HH>
#   Device ID + Sensor ID + Date Hour
# 
# Sort key:
#   time#<MM>
#   Minutes    

def get_minutes_table(mode='dev'):
    table_name = f"{mode}-blackout-monitor-minutes"
    return get_table(table_name)    

def get_hours_table(mode='dev'):
    table_name = f"{mode}-blackout-monitor-hours"
    return get_table(table_name) 

def get_days_table(mode='dev'):
    table_name = f"{mode}-blackout-monitor-days"
    return get_table(table_name) 

def get_table(table_name):
    try:
        table = dynamodb.Table(table_name)
        table.load()
        return table
    except ClientError as err:
        logging.warning(f'Table {table_name} not found, creating it')
        if err.response["Error"]["Code"] == "ResourceNotFoundException":
            return create_table(table_name) 
        else:
            logger.error(
                "Couldn't check for existence of %s. Here's why: %s: %s",
                table_name,
                err.response["Error"]["Code"],
                err.response["Error"]["Message"],
            )
            raise

# Function to query the first unprocessed item in the table and returns partition key
# unprocessed item means status = new
def query_first_pk_to_aggregate(table_name,device_id, sensor_id):
    try:
        table = get_table(table_name)
        resp = table.query(
            IndexName="sk_status-index",
            # AttributesToGet=['pk'],           
            KeyConditionExpression=Key('pk_status').eq(f'device#{device_id}#sensor#{sensor_id}#status#new'),
            Limit=1
        )
        logger.debug(f"Read unprocessed item {table_name} device_id {device_id} sensor_id {sensor_id}; Query response: {resp}")        
        return  resp['Items'][0]['pk'] if 'Items' in resp and len(resp['Items']) > 0  else None
       
    except Exception as err:
        logger.error(f"Couldn't read table {table_name} device_id {device_id} sensor_id {sensor_id}")
        logger.exception(err)
        raise

# Function to query table items
# by partition key and optionally by sort key
# ExclusiveStartKey is used for pagination
def query_data_by_pk(table_name,pk, sk=None,ExclusiveStartKey=None):
    try:
        table = get_table(table_name)
        items = []

        KeyConditionExpression = Key('pk').eq(pk) if sk is None else Key('pk').eq(pk) & Key('sk').eq(sk)

        if ExclusiveStartKey is None:
            resp = table.query(
                KeyConditionExpression=KeyConditionExpression,
            )
        else:
            resp = table.query(
                KeyConditionExpression=KeyConditionExpression,
                ExclusiveStartKey=ExclusiveStartKey,
            )    
        logger.debug(f"Read items {table_name} pk {pk}  Items in response: {len(resp['Items'])}")  
        items.extend(resp['Items'])
        if 'LastEvaluatedKey' in resp:
            items.extend(query_data_by_pk(table_name,pk,sk,ExclusiveStartKey=resp['LastEvaluatedKey']))
        return items
    except Exception as err:
        logger.error(f"Couldn't read table {table_name} pk {pk} ExclusiveStartKey {ExclusiveStartKey}")
        logger.exception(err)
        raise

# Function to update status of items in the table to done from new
def update_status_as_done(table_name,items):
    try:
        i = 0
        table = get_table(table_name)
        for item in items:
            i += 1
            table.update_item(
                Key={
                    'pk': item['pk'],
                    'sk': item['sk']
                },
                UpdateExpression='SET pk_status = :pk_status',
                ExpressionAttributeValues={
                    ':pk_status': item['pk_status'].replace('status#new', 'status#done')
                }
            )
          
        
        logger.debug(f"Updated  status to Done {i} items  pk {items[0]['pk']} ")  
        
  
    except Exception as err:
        logger.error(f"Couldn't update_status {table_name} ")
        logger.exception(err)
        raise



def create_table(table_name):
    try:
        logger.info(f"Creating DynamoDB table {table_name}")    
        table =  dynamodb.create_table(
            TableName=table_name,
            KeySchema=[
                {"AttributeName": "pk", "KeyType": "HASH"},   # Partition key;
                {"AttributeName": "sk", "KeyType": "RANGE"},  # Sort key
            ],
            AttributeDefinitions=[
          
                {"AttributeName": "pk", "AttributeType": "S"},   
                {"AttributeName": "sk", "AttributeType": "S"},  # Sort key
                # Device ID + Sensor ID + Status of record - new or done
                # device#<device_id>#sensor#<sensor_id>#date#<YYYY-MM-DD-HH>status#<new|done>
                {"AttributeName": "pk_status", "AttributeType": "S"},                
                # ISO 8601 timestamp
                {"AttributeName": "ts", "AttributeType": "S"},
            ],
            #optimize search by status
            GlobalSecondaryIndexes=[
            {
                'IndexName': 'sk_status-index',
                'KeySchema': [           
                    {'AttributeName': 'pk_status','KeyType': 'HASH'} , # Partition key  
                    {"AttributeName": "ts", "KeyType": "RANGE"},       # Sort key
                ],
                'Projection': {
                    'ProjectionType': 'ALL'
                }
            }
            ],

            BillingMode='PAY_PER_REQUEST'
        )
        table.wait_until_exists()

    except ClientError as err:
        logger.error(
            "Couldn't create table %s. Here's why: %s: %s",
            table_name,
            err.response["Error"]["Code"],
            err.response["Error"]["Message"],
        )
        raise
    else:
        return table
    