import boto3
from botocore.exceptions import ClientError
import time
import json


def create_annotation_job_request(n, key):
    # Parse redirect URL query parameters for S3 object info
    bucket_name = 'gas-inputs'
    key_name = key

    results_bucket_name = 'gas-results'
    sns_job_request_topic = "arn:aws:sns:us-east-1:127134666975:hongleizhou_job_requests"

    # Extract the job ID from the S3 key
    job_id = key_name.split('/')[2].split('~')[0]
    file_name = key_name.split('/')[2].split('~')[1]
    user_id = key_name.split('/')[1]
    email = 'hongleizhou@ucmpcs.org'

    # Persist job to database
    try:
        dynamodb = boto3.resource('dynamodb', region_name="us-east-1")
        ann_table = dynamodb.Table('hongleizhou_annotations')

        data = {'job_id': job_id,
                'user_id': user_id,
                'email': email,
                'submit_time': int(time.time()),
                'input_file_name': file_name,
                's3_inputs_bucket': bucket_name,
                's3_key_input_file': key_name,
                's3_results_bucket': results_bucket_name,
                'job_status': 'PENDING'
                }

        ann_table.put_item(Item=data)

        data['url'] = 'https://hongleizhou.ucmpcs.org/annotations/00846e5a-39ef-4ce6-af73-4901c7e83301'
        data['role'] = 'premium_user'
        sns = boto3.resource('sns', region_name="us-east-1")
        topic = sns.Topic(sns_job_request_topic)
        topic.publish(Message=json.dumps(data))
        print("Message {} sent: {} ".format(n, data))
    except ClientError as e:
        print(e)


if __name__ == '__main__':
    i = 0
    keys = ['hongleizhou/03e37750-887e-4c60-a975-2f8e9b3f190e/1d51fc86-f189-461d-8a10-c467feebe897~free_1.vcf',
            'hongleizhou/03e37750-887e-4c60-a975-2f8e9b3f190e/281c72f6-f548-4425-b2a2-979f639591de~free_1.vcf',
            'hongleizhou/03e37750-887e-4c60-a975-2f8e9b3f190e/351391fc-62f6-49ea-83d2-888115018f1d~free_1.vcf',
            'hongleizhou/03e37750-887e-4c60-a975-2f8e9b3f190e/46cde16f-5a9f-43e6-827d-418a0266f5d8~free_1.vcf',
            'hongleizhou/03e37750-887e-4c60-a975-2f8e9b3f190e/5810414b-bec6-412c-a8cc-a42e7084669e~free_2.vcf']
    while True:
        create_annotation_job_request(i, keys[i % 5])
        time.sleep(20)
        i = i + 1
