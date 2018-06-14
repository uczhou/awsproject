import subprocess
import boto3
import json
from botocore.exceptions import ClientError
import config_init
import sys

app_config = config_init.UtilsConfig()

# ref: http://boto3.readthedocs.io/en/latest/reference/services/s3.html#bucket
# Create s3 client
s3 = boto3.resource('s3', region_name=app_config.AWS_REGION_NAME)

# ref: http://boto3.readthedocs.io/en/latest/guide/sqs.html
# Create sqs client
sqs = boto3.resource('sqs', region_name=app_config.AWS_REGION_NAME)
queue = sqs.get_queue_by_name(QueueName=app_config.AWS_SQS_JOB_REQUEST_NAME)

# Looping to retrieve messages from SQS
while True:
    messages = queue.receive_messages(MaxNumberOfMessages=10, WaitTimeSeconds=5)
    if len(messages) == 0:
        continue

    for message in messages:
        data = json.loads(json.loads(message.body)['Message'])

        try:
            bucket = data['s3_inputs_bucket']
            key = data['s3_key_input_file']
            file_info = key.split('/')[2]
            results_bucket = data['s3_results_bucket']
            user_id = data['user_id']
            job_id = data['job_id']
            email = data['email']
            url = data['url']
            role = data['role']
            file_path = app_config.LOCAL_DATA_PREFIX + file_info
            print('File Path: {}'.format(file_path))
            print('Key: {}'.format(key))

            status = 'PENDING'

            # ref: http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Bucket.download_file
            # Download file from s3 bucket
            s3.Bucket(bucket).download_file(key, file_path)

            # Run the annotator
            subprocess.Popen([sys.executable, 'run.py', file_path, user_id, email, url, role])

            status = "RUNNING"

            print(status)
            # Create dynamodb client
            dynamodb = boto3.resource('dynamodb', region_name=app_config.AWS_REGION_NAME)

            # Update dynamodb
            # ref: https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
            ann_table = dynamodb.Table(app_config.AWS_DYNAMODB_ANNOTATIONS_TABLE)
            ann_table.update_item(
                Key={
                    'job_id': job_id
                },
                UpdateExpression="set job_status = :running",
                ConditionExpression="job_status = :pending",
                ExpressionAttributeValues={
                    ':pending': 'PENDING',
                    ':running': status
                },
                ReturnValues="ALL_NEW"
            )

            message.delete()

            print('Job submitted successfully')

        except ClientError as e:
            message.delete()
            print(e)
            continue
