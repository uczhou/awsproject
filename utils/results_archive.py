import boto3
from boto3.dynamodb.conditions import Key
import json
from botocore.exceptions import ClientError
import config_init
import time

app_config = config_init.UtilsConfig()

# Create s3 client
s3 = boto3.resource('s3', region_name=app_config.AWS_REGION_NAME)

# Create sqs, sns client
# ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
# ref: http://boto3.readthedocs.io/en/latest/guide/sqs.html
sqs = boto3.resource('sqs', region_name=app_config.AWS_REGION_NAME)
sns = boto3.resource('sns', region_name=app_config.AWS_REGION_NAME)

# sns topic
sns_job_archive_topic = app_config.AWS_SNS_JOB_ARCHIVE_TOPIC
sns_job_restore_topic = app_config.AWS_SNS_JOB_RESTORE_TOPIC

sns_topic = sns.Topic(sns_job_archive_topic)
sns_restore_topic = sns.Topic(sns_job_restore_topic)

# sqs
queue = sqs.get_queue_by_name(QueueName=app_config.AWS_SQS_JOB_ARCHIVE_NAME)

# Create dynamodb client
# ref: https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
# ref: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
dynamodb = boto3.resource('dynamodb', region_name=app_config.AWS_REGION_NAME)
table = dynamodb.Table(app_config.AWS_DYNAMODB_ANNOTATIONS_TABLE)

# Create glacier client
# ref: http://boto3.readthedocs.io/en/latest/reference/services/glacier.html
glacier_client = boto3.client('glacier', region_name=app_config.AWS_REGION_NAME)


def __archive_data__(source, destination, key):
    '''
    Helper function used to upload user data from s3 to glacier.
    :param source:
    :param destination:
    :param key:
    :return:
    '''
    # ref: http://boto3.readthedocs.io/en/latest/reference/services/glacier.html#Glacier.Client.upload_archive
    # ref: https://stackoverflow.com/questions/41833565/s3-buckets-to-glacier-on-demand-is-it-possible-from-boto3-api
    obj = s3.Object(source, key)
    response = glacier_client.upload_archive(vaultName=destination, body=obj.get()['Body'].read())
    print('Archive data successfully. archive_id: {}'.format(response))
    return response['archiveId']


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


def __user_helper__(item, action, base_url, email):
    '''
    Helper function used to send archive message to sns and update dynamodb
    :param item:
    :param action:
    :return:
    '''
    print(item)
    message = {
        'type': 'job',
        'user_id': item['user_id'],
        'id': item['job_id'],
        'action': action,
        's3_key_result_file': item['s3_key_result_file'],
        'initiated': False,
        'complete_time': int(item['complete_time']),
        'url': base_url,
        'email': email
    }
    if 'archiveId' in item:
        message.update({'archiveId': item['archiveId']})
    sns_topic.publish(Message=json.dumps(message))


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
            if data['type'] == 'user':
                response = table.query(
                    IndexName='user_id_index',
                    KeyConditionExpression=Key('user_id').eq(data['id'])
                )

                items = response['Items']

                # archive files
                if data['action'] == 'archive':
                    for item in items:
                        if 'archived' not in item or item['archived'] is False:
                            print('Archive Item: '.format(item['job_id']))
                            __user_helper__(item, 'archive', data['url'], data['email'])

                # restore files
                elif data['action'] == 'restore':
                    for item in items:
                        if 'archived' in item and item['archived'] is True:
                            print('Restore Item: '.format(item['job_id']))
                            __user_helper__(item, 'restore', data['url'], data['email'])

                message.delete()
            elif data['type'] == 'job':

                # action: archive
                if data['action'] == 'archive':

                    complete_time = data['complete_time']
                    results_bucket = app_config.AWS_S3_RESULTS_BUCKET
                    # check if still in free download period.
                    if int(time.time()) - complete_time > app_config.FREE_USER_DATA_RETENTION:

                        # archive the file
                        archive_id = __archive_data__(app_config.AWS_S3_RESULTS_BUCKET,
                                                      app_config.AWS_GLACIER_VAULT, data['s3_key_result_file'])

                        # update to the database
                        __update_db__(data['id'], archive_id, True)

                        # delete file from s3
                        s3.Object(app_config.AWS_S3_RESULTS_BUCKET, data['s3_key_result_file']).delete()

                        message.delete()
                elif data['action'] == 'restore':
                    # initiate the restore.
                    jobParameters = {
                        "Type": "archive-retrieval",
                        "ArchiveId": data['archiveId'],
                        "Tier": "Expedited",
                    }

                    # ref: http://boto3.readthedocs.io/en/latest/reference/services/glacier.html#Glacier.Client.initiate_job
                    response = glacier_client.initiate_job(
                        vaultName=app_config.AWS_GLACIER_VAULT,
                        jobParameters=jobParameters
                    )

                    print('Initiate job response: {}'.format(response))

                    data['initiated'] = True
                    data.update({'jobId': response['jobId']})
                    sns_restore_topic.publish(Message=json.dumps(data))

                    message.delete()
        except ClientError as e:
            print(e)
            continue
