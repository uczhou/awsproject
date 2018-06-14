# Copyright (C) 2011-2018 Vas Vasiliadis
# University of Chicago
##
__author__ = 'Vas Vasiliadis <vas@uchicago.edu>'

import sys
import time
import driver
import boto3
import subprocess
from botocore.exceptions import ClientError
import config_init
import json
from urllib.parse import urljoin

"""A rudimentary timer for coarse-grained profiling
"""


class Timer(object):
    def __init__(self, verbose=True):
        self.verbose = verbose

    def __enter__(self):
        self.start = time.time()
        return self

    def __exit__(self, *args):
        self.end = time.time()
        self.secs = self.end - self.start
        if self.verbose:
            print("Total runtime: {0:.6f} seconds".format(self.secs))


def __update_status__(annotations_table, job_id, results_bucket, ann_key, log_key, status, complete_time):
    '''
    Helper function used to update job status in dynamodb
    :param annotations_table:
    :param job_id:
    :param results_bucket:
    :param ann_key:
    :param log_key:
    :param status:
    :param complete_time:
    :return:
    '''
    # ref: https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
    dynamodb = boto3.resource('dynamodb', region_name='us-east-1')
    ann_table = dynamodb.Table(annotations_table)
    ann_table.update_item(
        Key={
            'job_id': job_id
        },
        UpdateExpression="set  s3_results_bucket= :bucket, s3_key_result_file=:result, "
                         "s3_key_log_file=:log, complete_time=:time, job_status=:status",
        ExpressionAttributeValues={
            ':bucket': results_bucket,
            ':result': ann_key,
            ':log': log_key,
            ':time': complete_time,
            ':status': status
        },
        ReturnValues="ALL_NEW"
    )


def __publish_complete_status__(user_id, job_id, email, url, complete_topic):
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
    request_url = urljoin(url, '/annotations/'+job_id)
    data = {'job_id': job_id,
            'user_id': user_id,
            'email': email,
            'url': request_url
            }

    sns = boto3.resource('sns', region_name=app_config.AWS_REGION_NAME)
    topic = sns.Topic(complete_topic)
    topic.publish(Message=json.dumps(data))
    print('Publish message: {}'.format(data))


def __publish_archive_status__(job_id, ann_key, complete_time):
    '''
    Helper function used to publish archive message to SNS
    :param job_id:
    :param ann_key:
    :param complete_time:
    :return:
    '''
    # ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
    data = {'id': job_id,
            'type': 'job',
            'action': 'archive',
            'complete_time': complete_time,
            'initiated': False,
            's3_key_result_file': ann_key
            }

    sns = boto3.resource('sns', region_name=app_config.AWS_REGION_NAME)
    topic = sns.Topic(app_config.AWS_SNS_JOB_ARCHIVE_TOPIC)
    topic.publish(Message=json.dumps(data))
    print('Publish message: {}'.format(data))


def __upload_file__(results_bucket, ann_file, ann_key, log_file, log_key):
    '''
    Helper function used to upload files to s3 buckets.
    :param results_bucket:
    :param ann_file:
    :param ann_key:
    :param log_file:
    :param log_key:
    :return:
    '''
    # ref: https://stackoverflow.com/questions/37017244/uploading-a-file-to-a-s3-bucket-with-a-prefix-using-boto3
    s3 = boto3.resource('s3', region_name=app_config.AWS_REGION_NAME)
    s3.meta.client.upload_file(ann_file, results_bucket, ann_key)
    s3.meta.client.upload_file(log_file, results_bucket, log_key)


if __name__ == '__main__':
    # Call the AnnTools pipeline
    if len(sys.argv) > 1:
        with Timer():
            driver.run(sys.argv[1], 'vcf')

        app_config = config_init.UtilsConfig()
        results_bucket = app_config.AWS_S3_RESULTS_BUCKET
        log_suffix = '.vcf.count.log'
        ann_suffix = '.annot.vcf'

        file_name = sys.argv[1].split('/')[1].split('.')[0]
        user_id = sys.argv[2]
        job_id = file_name.split('~')[0]
        email = sys.argv[3]
        url = sys.argv[4]
        role = sys.argv[5]
        ann_file = app_config.LOCAL_DATA_PREFIX + file_name + ann_suffix
        log_file = app_config.LOCAL_DATA_PREFIX + file_name + log_suffix
        ann_key = app_config.AWS_S3_KEY_PREFIX + user_id + '/' + file_name + ann_suffix
        log_key = app_config.AWS_S3_KEY_PREFIX + user_id + '/' + file_name + log_suffix

        complete_time = int(time.time())

        try:
            # upload files to s3
            __upload_file__(results_bucket, ann_file, ann_key, log_file, log_key)

            print('Update dynamodb successfully')

            # publish job completion message
            __publish_complete_status__(user_id, job_id, email, url, app_config.AWS_SNS_JOB_COMPLETE_TOPIC)

            # check if user is free_user, if yes, send archive message to SNS.
            if role == 'free_user':
                __publish_archive_status__(job_id, ann_key, complete_time)

            # update status in dynamodb
            __update_status__(app_config.AWS_DYNAMODB_ANNOTATIONS_TABLE,
                              job_id, results_bucket, ann_key, log_key, 'COMPLETED', complete_time)

        except ClientError as e:

            print(e)
            # if job failed,update job status as Failed in dynamodb
            __update_status__(app_config.AWS_DYNAMODB_ANNOTATIONS_TABLE,
                              job_id, results_bucket, ann_key, log_key, 'FAILED', complete_time)

        finally:
            # Clean up (delete) local job files
            subprocess.Popen(['rm', '-f', sys.argv[1]])
            subprocess.Popen(['rm', '-f', ann_file])
            subprocess.Popen(['rm', '-f', log_file])

    else:
        print("A valid .vcf file must be provided as input to this program.")