import boto3
import json
import os
from datetime import datetime

comprehend = boto3.client('comprehend')
dynamodb = boto3.client('dynamodb')
s3 = boto3.client('s3')

def extract_text_from_transcribe_result(bucket, key):
    """Get transcription text from Transcribe output"""
    try:
        response = s3.get_object(Bucket=bucket, Key=key)
        print(response)
        transcribe_result = json.loads(response['Body'].read().decode('utf-8'))
        
        # Extract useful information
        text = transcribe_result['results']['transcripts'][0]['transcript']
        confidence = transcribe_result['results'].get('items', [{}])[0].get('confidence', 0)
        
        return {
               'text': text,
            'confidence': confidence
        }
    except Exception as e:
        print(f"Error extracting text: {str(e)}")
        raise

def analyze_text(text):
    """Analyze text using Comprehend"""
    try:
        # Get key phrases (limited to first 5KB if text is too long)
        text_chunk = text[:5000] if len(text) > 5000 else text
        
        key_phrases_response = comprehend.detect_key_phrases(
            Text=text_chunk,
            LanguageCode='en'
        )

        sentiment_response = comprehend.detect_sentiment(
            Text=text_chunk,
            LanguageCode='en'
        )

        entities_response = comprehend.detect_entities(
            Text=text_chunk,
            LanguageCode='en'
        )

        return {
            'keyPhrases': key_phrases_response['KeyPhrases'],
            'sentiment': sentiment_response['Sentiment'],
            'sentimentScores': sentiment_response['SentimentScore'],
            'entities': entities_response['Entities']
        }
    except Exception as e:
        print(f"Error in text analysis: {str(e)}")
        raise

def lambda_handler(event, context):
    try:
        # Get bucket and file details from S3 event
        bucket = event['Records'][0]['s3']['bucket']['name']
        key = event['Records'][0]['s3']['object']['key']

        if 'temp' in key:
            return {
                'statusCode': 400,
                'body': json.dumps({
                    'error': 'This is the temp file'
                })
            }
        
        # Extract user_id and job_name from key (format: user_id/jobname.json)
        user_id = key.split('/')[0]
        job_name = key.split('/')[-1].split('.')[0]
        
        # Get transcricribed text
        transcribe_result = extract_text_from_transcribe_result(bucket, key)
        text = transcribe_result['text']
        
        # Analyze with Comprehend
        analysis_result = analyze_text(text)
        
        # Store results in DynamoDB
        dynamodb.put_item(
            TableName=os.environ['TRANSCRIBE_RESULTS_TABLE'],
            Item={
                'user_id': {'S': user_id},
                'job_name': {'S': job_name},
                'timestamp': {'S': datetime.now().isoformat()},
                'transcript': {'S': text},
                'confidence': {'N': str(transcribe_result['confidence'])},
                'key_phrases': {'S': json.dumps([{
                    'text': phrase['Text'],
                    'score': phrase['Score']
                } for phrase in analysis_result['keyPhrases']])},
                'sentiment': {'S': analysis_result['sentiment']},
                'sentiment_scores': {'S': json.dumps(analysis_result['sentimentScores'])},
                'entities': {'S': json.dumps([{
                    'text': entity['Text'],
                    'type': entity['Type'],
                    'score': entity['Score']
                } for entity in analysis_result['entities']])},
                'status': {'S': 'COMPLETED'}
            }
        )
        
        print(f"Analysis complete for job: {job_name}, user: {user_id}")
        
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Analysis complete',
                'jobName': job_name,
                'userId': user_id
            })
        }
        
    except Exception as e:
        print(f"Error: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
