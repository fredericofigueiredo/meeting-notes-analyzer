import boto3
import json
import os
from datetime import datetime

transcribe = boto3.client('transcribe')
s3 = boto3.client('s3')

SUPPORTED_FORMATS = {
    'amr': 'amr',
    'flac': 'flac',
    'm4a': 'm4a',
    'mp3': 'mp3',
    'mp4': 'mp4',
    'ogg': 'ogg',
    'webm': 'webm',
    'wav': 'wav'
}

MAX_FILE_SIZE_MB = int(os.environ['MAX_FILE_SIZE_MB'])

def get_media_format(key):
    print(key)
    """Get and validate media format from file extension"""
    file_ext = key.lower().split('.')[1]
    print(file_ext)
    
    if file_ext not in SUPPORTED_FORMATS:
        raise ValueError(f"Unsupported media format: {file_ext}. Supported formats: {', '.join(SUPPORTED_FORMATS.keys())}")
    
    return SUPPORTED_FORMATS[file_ext]

def check_file_limits(bucket, key):
    """Check if file meets size limits"""
    response = s3.head_object(Bucket=bucket, Key=key)
    file_size_mb = response['ContentLength'] / (1024 * 1024)
    
    if file_size_mb > MAX_FILE_SIZE_MB:
        raise ValueError(f"File size ({file_size_mb:.2f}MB) exceeds limit of {MAX_FILE_SIZE_MB}MB")
    
    return True

def lambda_handler(event, context):
    #try:
    # Get bucket and file details from S3 event
    bucket = event['Records'][0]['s3']['bucket']['name']
    key = event['Records'][0]['s3']['object']['key']
    
    # Extract user_id from path (assuming format: user_id/filename.ext)
    user_id = key.split('/')[0]
    original_filename = key.split('/')[-1]
    
    # Validate file
    check_file_limits(bucket, key)
    media_format = get_media_format(key)
    
    # Create unique job name including user_id
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    job_name = f"transcribe-{user_id}-{timestamp}"
    
    # Start transcription job
    print(f"s3://{bucket}/{key}")
    response = transcribe.start_transcription_job(
        TranscriptionJobName=job_name,
        Media={
            'MediaFileUri': f"s3://{bucket}/{key}"
        },
        MediaFormat=media_format,
        LanguageCode='en-US',
        OutputBucketName=os.environ['OUTPUT_BUCKET_FILE'],
        OutputKey=f"{user_id}/{job_name}.json"  # Organize outputs by user
    )
    
    print(f"Started transcription job: {job_name} for user: {user_id}, file: {original_filename}")
    
    return {
        'statusCode': 200,
        'body': json.dumps({
            'message': 'Transcription job started',
            'jobName': job_name,
            'userId': user_id,
            'originalFile': original_filename
        })
    }
        
    # except ValueError as ve:
    #     print(f"Validation Error: {str(ve)}")
    #     return {
    #         'statusCode': 400,
    #         'body': json.dumps({
    #             'error': str(ve)
    #         })
    #     }
    # except Exception as e:
    #     print(f"Error: {str(e)}")
    #     return {
    #         'statusCode': 500,
    #         'body': json.dumps({
    #             'error': str(e)
    #         })
    #     }
