import boto3
import json
from botocore.exceptions import ClientError
import config_init

app_config = config_init.UtilsConfig()

# Create s3 client
s3 = boto3.resource('s3', region_name=app_config.AWS_REGION_NAME)

# Create sqs client
# ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
# ref: http://boto3.readthedocs.io/en/latest/guide/sqs.html
sqs = boto3.resource('sqs', region_name=app_config.AWS_REGION_NAME)
queue = sqs.get_queue_by_name(QueueName=app_config.AWS_SQS_JOB_COMPLETE_NAME)


# ref: adapted from utils.py
def send_email_ses(recipients=None, sender=None, subject=None, body=None):

    ses = boto3.client('ses', region_name=app_config.AWS_REGION_NAME)

    response = ses.send_email(
        Destination={'ToAddresses': recipients},
        Message={
          'Body': {'Text': {'Charset': "UTF-8", 'Data': json.dumps(body)}},
          'Subject': {'Charset': "UTF-8", 'Data': subject},
        },
        Source=sender)
    print('Send message: from {} to {}, content: {}'.format(sender, recipients, body))
    return response['ResponseMetadata']['HTTPStatusCode']


# Looping to retrieve messages from SQS
while True:
    messages = queue.receive_messages(MaxNumberOfMessages=10, WaitTimeSeconds=5)
    if len(messages) == 0:
        continue

    for message in messages:
        data = json.loads(json.loads(message.body)['Message'])
        try:
            user_id = data['user_id']
            job_id = data['job_id']
            email = data['email']
            subject = 'Annotation result is ready to view.'
            # send information to user email when job is done.
            url = data['url']
            body = {
                'job_id': job_id,
                'url': url
            }
            send_email_ses(recipients=[email], sender=app_config.MAIL_DEFAULT_SENDER, subject=subject, body=body)
            message.delete()
        except ClientError as e:
            print(e)
            message.delete()
            continue
