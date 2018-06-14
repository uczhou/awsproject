import boto3
import json
from botocore.exceptions import ClientError
import config_init
from urllib.parse import urljoin

app_config = config_init.UtilsConfig()

# Create s3 client
s3 = boto3.resource('s3', region_name=app_config.AWS_REGION_NAME)

# Create sqs, sns client
# ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
# ref: http://boto3.readthedocs.io/en/latest/guide/sqs.html
sqs = boto3.resource('sqs', region_name=app_config.AWS_REGION_NAME)
sns = boto3.resource('sns', region_name=app_config.AWS_REGION_NAME)

sns_job_complete_topic = app_config.AWS_SNS_JOB_COMPLETE_TOPIC

queue = sqs.get_queue_by_name(QueueName=app_config.AWS_SQS_JOB_RESTORE_NAME)
sns_topic = sns.Topic(sns_job_complete_topic)

# Create dynamodb client
# ref: https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
# ref: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
dynamodb = boto3.resource('dynamodb', region_name=app_config.AWS_REGION_NAME)
table = dynamodb.Table(app_config.AWS_DYNAMODB_ANNOTATIONS_TABLE)

# Create glacier client
# ref: http://boto3.readthedocs.io/en/latest/reference/services/glacier.html
glacier_client = boto3.client('glacier', region_name=app_config.AWS_REGION_NAME)


def __restore_data__(jobId, key):
    '''
    Helper function used to restore files from glacier to s3 bucket.
    :param jobId:
    :param key:
    :return:
    '''

    # ref: https://stackoverflow.com/questions/46950884/archive-retrieval-from-aws-glacier
    # ref: http://boto3.readthedocs.io/en/latest/reference/services/glacier.html#Glacier.Client.get_job_output
    # ref: http://boto3.readthedocs.io/en/latest/reference/services/glacier.html#Glacier.Client.describe_job
    response = glacier_client.describe_job(
        vaultName=app_config.AWS_GLACIER_VAULT,
        jobId=jobId
    )

    print('Describe job response: {}'.format(response))

    if response['Completed'] is True:
        output = glacier_client.get_job_output(
            vaultName=app_config.AWS_GLACIER_VAULT,
            jobId=jobId
        )
        obj = s3.Object(app_config.AWS_S3_RESULTS_BUCKET, key)
        stream_data = output['body'].read()
        # https://stackoverflow.com/questions/40336918/how-to-write-a-file-or-data-to-an-s3-object-using-boto3/40336919
        obj.put(Body=stream_data)
        print('Restored data. File size: {}'.format(output['contentType']))
        return True
    else:
        print('Restore data failed. jobID: {}'.format(jobId))
        return False


def __update_db__(job_id, archiveId, archived):
    '''
    Helper function used to update dynamodb
    :param job_id:
    :param archiveId:
    :param archived:
    :return:
    '''
    table.update_item(
        Key={
            'job_id': job_id
        },
        UpdateExpression="set  archiveId= :archiveId, archived= :archived",
        ExpressionAttributeValues={
            ':archiveId': archiveId,
            ':archived': archived
        },
        ReturnValues="ALL_NEW"
    )

    print('Update dynamodb successfully. archivedID: {}, archived: {}'.format(archiveId, archived))


def __publish_complete_status__(data):
    '''
    Helper function used to publish job completion message to SNS.
    :param user_id:
    :param job_id:
    :param email:
    :param url:
    :param complete_topic:
    :return:
    '''
    # ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
    url = data['url']
    job_id = data['id']
    user_id = data['user_id']
    email = data['email']
    request_url = urljoin(url, '/annotations/'+job_id)
    data = {'job_id': job_id,
            'user_id': user_id,
            'email': email,
            'url': request_url
            }

    sns_topic.publish(Message=json.dumps(data))
    print('Publish message: {}'.format(data))


# Looping to retrieve messages from SQS
while True:
    messages = queue.receive_messages(MaxNumberOfMessages=10, WaitTimeSeconds=5)
    if len(messages) == 0:
        continue

    # process messages
    for message in messages:

        data = json.loads(json.loads(message.body)['Message'])
        print('Received message: {}'.format(data))
        try:
            if __restore_data__(data['jobId'], data['s3_key_result_file']) is True:
                # update to the database if restore succeed and delete the message.
                __update_db__(data['id'], data['archiveId'], False)

                __publish_complete_status__(data)

                message.delete()
        except ClientError as e:
            print(e)
            continue
