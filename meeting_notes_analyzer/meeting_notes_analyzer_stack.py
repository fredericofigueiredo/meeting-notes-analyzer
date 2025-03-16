from aws_cdk import (
    # Duration,
    Stack,
    # aws_sqs as sqs,
    aws_s3,
    aws_dynamodb,
    aws_lambda,
    aws_iam,
    aws_apigateway,
    aws_s3_notifications,
    Duration,
)
from constructs import Construct

class MeetingNotesAnalyzerStack(Stack):

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        #-------------------------------DYNAMO DB-------------------------------


        """
        DynamoDB table to store the results of Amazon Transcribe job
        """
        transcribe_results_table = aws_dynamodb.Table(
            self,
            "TranscribeResultsDDBTable",
            table_name="mna-transcribe-results-table",
            partition_key=aws_dynamodb.Attribute(
                name="user_id", 
                type=aws_dynamodb.AttributeType.STRING
            ),
            sort_key=aws_dynamodb.Attribute(
                name="timestamp",
                type=aws_dynamodb.AttributeType.STRING
            ),
            billing_mode=aws_dynamodb.BillingMode.PAY_PER_REQUEST,
            encryption=aws_dynamodb.TableEncryption.AWS_MANAGED,
            point_in_time_recovery=True

        )

        #-------------------------------LAMBDAS-------------------------------

        """
        Lambda function to trigger Amazon Transcribe job with mna-transcribe-role
        """

        transcribe_lambda = aws_lambda.Function(
            self,
            "TranscribeLambda",
            function_name="mna-transcribe-lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            code=aws_lambda.Code.from_asset("meeting_notes_analyzer/lambda/transcribe_lambda"),
            handler="transcribe_lambda.lambda_handler",
            timeout=Duration.minutes(5),  # Add timeout
            memory_size=128,  # Add memory limit
        )

        """
        Lambda function to trigger Amazon Comprehend job
        """
        comprehend_lambda = aws_lambda.Function(
            self,
            "ComprehendLambda",
            function_name="mna-comprehend-lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            code=aws_lambda.Code.from_asset("meeting_notes_analyzer/lambda/comprehend_lambda"),
            handler="comprehend_lambda.lambda_handler",
            environment={
                "TRANSCRIBE_RESULTS_TABLE": transcribe_results_table.table_name
            },
            timeout=Duration.minutes(5),  # Add timeout
            memory_size=128,  # Add memory limit
        )

        """
        Lambda connected to api gw to retrieve the results from dynamodb
        """
        get_results_lambda = aws_lambda.Function(
            self,
            "GetResultsLambda",
            function_name="mna-get-results-lambda",
            runtime=aws_lambda.Runtime.PYTHON_3_9,
            code=aws_lambda.Code.from_asset("meeting_notes_analyzer/lambda/get_results_lambda"),
            handler="get_results_lambda.lambda_handler",
            environment={
                "TRANSCRIBE_RESULTS_TABLE": transcribe_results_table.table_name
            },
            timeout=Duration.minutes(5),  # Add timeout
            memory_size=128,  # Add memory limit
        )


        #-------------------------------S3 BUCKETS-------------------------------
        
        """ 
        S3 bucket to store the meeting notes
        """
        input_file_bucket = aws_s3.Bucket(
            self,
            "RawFileBucket",
            bucket_name="mna-raw-file-bucket",
            versioned=False,
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            encryption=aws_s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )

        input_file_bucket.add_object_created_notification(
            aws_s3_notifications.LambdaDestination(transcribe_lambda)
        )

        """
        S3 Bucket to save results from Amazon Transcribe
        """

        transcribe_file_bucket = aws_s3.Bucket(
            self,
            "TranscribeBucket",
            bucket_name = "mna-transcribe-file-bucket",
            versioned=False,
            block_public_access=aws_s3.BlockPublicAccess.BLOCK_ALL,
            encryption=aws_s3.BucketEncryption.S3_MANAGED,
            enforce_ssl=True
        )
        transcribe_file_bucket.add_object_created_notification(
            aws_s3_notifications.LambdaDestination(comprehend_lambda)
        )


        #-------------------------------API GATEWAY-------------------------------

        """
        API GW to receive the request, trigger the Lambda and return the results.
        """
        api_gw = aws_apigateway.RestApi(
            self,
            "GetResultsAPIGW",
            rest_api_name="mna-api-gw",
            description="API GW to receive the request, trigger the Lambda and return the results.",
            default_cors_preflight_options=aws_apigateway.CorsOptions(
                allow_origins=aws_apigateway.Cors.ALL_ORIGINS,
                allow_methods=['GET', 'OPTIONS'],
                allow_headers=['Content-Type', 'Authorization']
            )
        )

        # Add resource and method
        get_results = api_gw.root.add_resource('get-results')
        get_results.add_method(
            'GET',
            aws_apigateway.LambdaIntegration(get_results_lambda)
        )


        #-------------------------------IAM and OTHERS-------------------------------


        # input_file_bucket.add_to_resource_policy(
        #     aws_iam.PolicyStatement(
        #         actions=["s3:PutObject"],
        #         principals=[aws_iam.AnyPrincipal()],
        #         resources=[input_file_bucket.arn_for_objects("*")]
        #     )
        # )

        input_file_bucket.add_cors_rule(
            allowed_methods=[aws_s3.HttpMethods.PUT],
            allowed_origins=["*"]
        )
        
        transcribe_lambda.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "transcribe:StartTranscriptionJob",
                    "transcribe:GetTranscriptionJob"
                ],
                resources=[f"arn:aws:transcribe:{self.region}:{self.account}:transcription-job/*"]
            )
        )
        transcribe_lambda.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                resources=[
                    input_file_bucket.bucket_arn,
                    f"{input_file_bucket.bucket_arn}/*"
                ]
            )
        )


        comprehend_lambda.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "comprehend:DetectEntities",
                    "comprehend:DetectKeyPhrases",
                    "comprehend:DetectSentiment"
                ],
                resources=["*"]  # Comprehend doesn't support resource-level permissions
            )
        )
        comprehend_lambda.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "s3:GetObject",
                    "s3:ListBucket"
                ],
                resources=[
                    transcribe_file_bucket.bucket_arn,
                    f"{transcribe_file_bucket.bucket_arn}/*"
                ]
            )
        )
        comprehend_lambda.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "dynamodb:PutItem",
                    "dynamodb:UpdateItem"
                ],
                resources=[transcribe_results_table.table_arn]
            )
        )


        get_results_lambda.add_to_role_policy(
            aws_iam.PolicyStatement(
                actions=[
                    "dynamodb:GetItem",
                    "dynamodb:Query",
                    "dynamodb:Scan"  # Remove if not needed
                ],
                resources=[transcribe_results_table.table_arn]
            )
        )

        transcribe_lambda.add_environment(
            "INPUT_FILE_BUCKET",
            input_file_bucket.bucket_name,
        )
        transcribe_lambda.add_environment(
            "MAX_FILE_SIZE_MB",
            "5",
        )


        """
        IAM role to allow Amazon Transcribe to access S3 bucket
        """
        transcribe_role = aws_iam.Role(
            self,
            "TranscribeJobRole",
            role_name="mna-transcribe-role",
            assumed_by=aws_iam.ServicePrincipal("transcribe.amazonaws.com"),
            inline_policies={
                "AllowS3Access": aws_iam.PolicyDocument(
                    statements=[
                        aws_iam.PolicyStatement(
                            actions=[
                                "s3:GetObject",
                                "s3:PutObject",
                                "s3:ListBucket"
                            ],
                            resources=[
                                input_file_bucket.bucket_arn,
                                f"{input_file_bucket.bucket_arn}/*"
                            ]
                        )
                    ]
                )
            }
        )