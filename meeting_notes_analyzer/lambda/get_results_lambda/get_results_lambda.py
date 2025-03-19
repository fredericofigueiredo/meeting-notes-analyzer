import boto3
import json

def lambda_handler(event, context):
    print("Event:", event)
    try:
        user_id = event['queryStringParameters']['user_id']
        print(f"Get Results Lambda triggered for user: {user_id}")
    except Exception as e:
        print(f"Error parsing user_id from event: {str(e)}")
        return {
            'statusCode': 400,
            'body': 'Error parsing user_id from event'
        }
    dynamodb = boto3.resource('dynamodb')
    table = dynamodb.Table('mna-transcribe-results-table')
    try:
        response = table.get_item(Key={'user_id': str(user_id)})
        print(response)
        #print(item['Item'] for item in response['Items'])
        #get key phrases and transcript from response
        key_phrases = response['Item']['key_phrases']
        transcript = response['Item']['transcript']
        print(transcript)
        
        #check which was the highest overall sentiment
        sentiment_scores = response['Item']['sentiment_scores']
        sentiment_scores = json.loads(sentiment_scores)
        sentiment = max(sentiment_scores, key=sentiment_scores.get)
        print(sentiment)

        #format key phrases as a list of strings order by score from hifhest to lowest
        key_phrases = json.loads(key_phrases)
        key_phrases = [phrase['text'] for phrase in key_phrases]
        print(key_phrases)

    except Exception as e:
        print(f"Error getting item from DynamoDB: {str(e)}")
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': 'Error getting item from DynamoDB'})
        }
    
    return {
        'statusCode': 200,
        'headers': {
            'Content-Type': 'application/json',
            'Access-Control-Allow-Origin': '*'
        },
        'body': json.dumps({
            'transcript': transcript,
            'key_phrases': key_phrases,
            'sentiment': sentiment
        })
    }