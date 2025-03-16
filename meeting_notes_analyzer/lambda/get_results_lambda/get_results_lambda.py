import boto3
import json

def lambda_handler(event, context):
    print("Event:", event)
    return {
        'statusCode': 200,
        'body': 'Get Results Lambda triggered'
    }