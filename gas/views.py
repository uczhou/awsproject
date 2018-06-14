# views.py
#
#
# Application logic for the GAS
#
##
__author__ = 'Honglei Zhou <hongleizhou@uchicago.edu>'

import uuid
import time
import json
import boto3
from botocore.client import Config
from boto3.dynamodb.conditions import Key

from flask import (abort, flash, redirect, render_template, 
  request, session, url_for)

from gas import app, db
from decorators import authenticated, is_premium
from auth import get_profile, update_profile
from botocore.exceptions import ClientError


"""Start annotation request
Create the required AWS S3 policy document and render a form for
uploading an annotation input file using the policy document
"""


@app.route('/annotate', methods=['GET'])
@authenticated
def annotate():
    # Open a connection to the S3 service
    s3 = boto3.client('s3',
      region_name=app.config['AWS_REGION_NAME'],
      config=Config(signature_version='s3v4'))

    bucket_name = app.config['AWS_S3_INPUTS_BUCKET']
    user_id = session['primary_identity']

    # Generate unique ID to be used as S3 key (name)
    key_name = app.config['AWS_S3_KEY_PREFIX'] + user_id + '/' + str(uuid.uuid4()) + '~${filename}'

    # Redirect to a route that will call the annotator
    redirect_url = str(request.url) + "/job"

    # Get user profile
    profile = get_profile(identity_id=user_id)

    # Get limit size
    limit = -1
    if profile.role == 'free_user':
        limit = app.config['FREE_USER_FILE_LIMIT']

    session.update({'limit': limit})

    # Define policy conditions
    # NOTE: We also must inlcude "x-amz-security-token" since we're
    # using temporary credentials via instance roles
    encryption = app.config['AWS_S3_ENCRYPTION']
    acl = app.config['AWS_S3_ACL']
    expires_in = app.config['AWS_SIGNED_REQUEST_EXPIRATION']
    fields = {
      "success_action_redirect": redirect_url,
      "x-amz-server-side-encryption": encryption,
      "acl": acl
    }

    conditions = [
      ["starts-with", "$success_action_redirect", redirect_url],
      {"x-amz-server-side-encryption": encryption},
      {"acl": acl}
    ]

    # Generate the presigned POST call
    presigned_post = s3.generate_presigned_post(Bucket=bucket_name,
                                                Key=key_name, Fields=fields, Conditions=conditions, ExpiresIn=expires_in)

    # How to redirect to sign up for premium if file size exceeds limit?
    app.logger.info(presigned_post)
    # Render the upload form which will parse/submit the presigned POST
    return render_template('annotate.html', s3_post=presigned_post)


"""Fires off an annotation job
Accepts the S3 redirect GET request, parses it to extract 
required info, saves a job item to the database, and then
publishes a notification for the annotator service.
"""


@app.route('/annotate/job', methods=['GET'])
@authenticated
def create_annotation_job_request():
    # Parse redirect URL query parameters for S3 object info
    # ref: http://flask.pocoo.org/docs/1.0/reqcontext/
    bucket_name = request.args.get('bucket')
    key_name = request.args.get('key')

    results_bucket_name = app.config['AWS_S3_RESULTS_BUCKET']
    sns_job_request_topic = app.config['AWS_SNS_JOB_REQUEST_TOPIC']

    # Extract the job ID from the S3 key
    job_id = key_name.split('/')[2].split('~')[0]
    file_name = key_name.split('/')[2].split('~')[1]
    user_id = key_name.split('/')[1]
    email = get_profile(identity_id=user_id).email

    # Persist job to database
    try:
        # ref: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
        dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'])
        ann_table = dynamodb.Table('hongleizhou_annotations')
    except ClientError as e:
        app.logger.info(e)
        print(e)
        return forbidden(e)

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

    app.logger.info('Update Dynamodb: {}'.format(data))
    # Send message to request queue
    try:
        # ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
        data['url'] = request.url
        data['role'] = get_profile(identity_id=user_id).role
        sns = boto3.resource('sns', region_name=app.config['AWS_REGION_NAME'])
        topic = sns.Topic(sns_job_request_topic)
        topic.publish(Message=json.dumps(data))

        app.logger.info('Publish message to {}: {}'.format(topic, data))

        return render_template('annotate_confirm.html', job_id=job_id)
    except ClientError as e:
        app.logger.info(e)
        print(e)
        return forbidden(e)


"""List all annotations for the user
"""


@app.route('/annotations', methods=['GET'])
@authenticated
def annotations_list():

    # Get list of annotations to display
    # Query DynamoDB
    try:
        # ref: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
        dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'])
        table = dynamodb.Table(app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE'])
        response = table.query(
            IndexName='user_id_index',
            KeyConditionExpression=Key('user_id').eq(session['primary_identity'])
        )

        items = response['Items']
        annotations = []
        for item in items:
            job = dict()
            job['job_id'] = item['job_id']
            job['input_file_name'] = item['input_file_name']
            job['job_status'] = item['job_status']
            job['submit_time'] = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(item['submit_time']))
            job['url'] = str(request.url) + '/' + item['job_id']

            annotations.append(job)
            app.logger.info('User: {} retrieves the job: {}, user_id: '
                            '{}'.format(session['primary_identity'], item['job_id'], item['user_id']))
        return render_template('annotations.html', annotations=annotations)

    except ClientError as e:
        print(e)
        app.logger.info(e)
        return forbidden(e)


def __get_job__(id):
    '''
    Helper function used to retrieve item by job id from dynamodb
    :param id:
    :return:
    '''
    # ref: http://boto3.readthedocs.io/en/latest/guide/dynamodb.html
    # ref: https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
    dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'])
    table = dynamodb.Table(app.config['AWS_DYNAMODB_ANNOTATIONS_TABLE'])
    response = table.get_item(
        Key={
            'job_id': id
        }
    )
    return response['Item']


"""Display details of a specific annotation job
"""


@app.route('/annotations/<id>', methods=['GET'])
@authenticated
def annotation_details(id):
    try:

        job = __get_job__(id)

    except ClientError as e:
        return page_not_found(e)

    user_id = session['primary_identity']
    profile = get_profile(identity_id=user_id)
    if job['user_id'] != user_id:
        return forbidden("error")
    else:
        # return the detailed information
        result_url = None
        log_url = None
        # ref: http://boto3.readthedocs.io/en/latest/guide/s3.html
        s3 = boto3.client('s3', region_name=app.config['AWS_REGION_NAME'])
        annotations = {
            'job_id': job['job_id'],
            'submit_time': time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job['submit_time'])),
            'input_file_name': job['input_file_name'],
            'job_status': job['job_status']
        }
        if job['job_status'] == 'COMPLETED':
            complete_time = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(job['complete_time']))
            annotations.update({'complete_time': complete_time})
            # log url
            log_url = str(request.url) + "/log"
            # write log
            app.logger.info('log url: {}'.format(log_url))

            if 'archived' not in job or job['archived'] is None or job['archived'] is False:
                try:
                    params = {'Bucket': app.config['AWS_S3_RESULTS_BUCKET'], 'Key': job['s3_key_result_file']}
                    result_url = s3.generate_presigned_url('get_object', ExpiresIn=600, Params=params)
                except ClientError as e:
                    print(e)
                    app.logger.info(e)
                    return page_not_found(e)
            elif 'archived' in job and job['archived'] is True and profile.role == 'premium_user':
                try:
                    data = {
                        'type': 'user',
                        'id': user_id,
                        'action': 'restore',
                        'url': request.url,
                        'email': profile.email
                    }

                    # publish subscription message
                    __publish_archive_status__(data)
                except ClientError as e:
                    print(e)
                    app.logger.info(e)
                    return page_not_found(e)
        else:
            annotations.update({'complete_time': 'In progress'})
        # return result_url and log_url to user
        annotations.update({'result_url': result_url, 'log_url': log_url})
        return render_template('annotation_details.html', annotations=annotations)


"""Display the log file for an annotation job
"""


@app.route('/annotations/<id>/log', methods=['GET'])
@authenticated
def annotation_log(id):
    try:
        # ref: http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Object.get
        # ref: https://stackoverflow.com/questions/31976273/open-s3-object-as-a-string-with-boto3
        item = __get_job__(id)
        s3 = boto3.resource('s3', region_name='us-east-1')
        log_file = s3.Object(app.config['AWS_S3_RESULTS_BUCKET'], item['s3_key_log_file'])
        log_content = log_file.get()['Body'].read().decode('utf-8')
        log_content = log_content.replace("\n", '<br/>')
        # create a new html file
        return render_template('log.html', log_content=log_content)
    except ClientError as e:
        app.logger.info(e)
        print(e)
        return page_not_found(e)


def __publish_archive_status__(data):
    '''
    Helper function used to publish archive message
    :param data:
    :return:
    '''
    # ref: http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
    sns = boto3.resource('sns', region_name=app.config['AWS_REGION_NAME'])
    topic = sns.Topic(app.config['AWS_SNS_JOB_ARCHIVE_TOPIC'])
    topic.publish(Message=json.dumps(data))


"""Subscription management handler
"""

import stripe


def __delete_customer__(user_id):
    '''
    Helper function used to delete user information from subscription as well as subscribed table
    :param user_id:
    :return:
    '''
    # ref: https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
    dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'])
    customer_table = dynamodb.Table(app.config['AWS_DYNAMODB_CUSTOMERS_TABLE'])

    item = customer_table.get_item(
        Key={'user_id': user_id}
    )

    # ref: https://stripe.com/docs/api#delete_account
    stripe.api_key = app.config['STRIPE_SECRET_KEY']

    subscription = stripe.Subscription.retrieve(item['Item']['subscription_id'])
    subscription.delete(at_period_end=True)

    response = customer_table.delete_item(
        Key={'user_id': user_id}
    )

    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    else:
        return False


def __add_customer__(user_id, customer_info):
    '''
    Helper function used to add customer information into subscription table when user subscribing to premium plan.
    :param user_id:
    :param customer_info:
    :return:
    '''
    dynamodb = boto3.resource('dynamodb', region_name=app.config['AWS_REGION_NAME'])
    customer_table = dynamodb.Table(app.config['AWS_DYNAMODB_CUSTOMERS_TABLE'])
    data = {
        'user_id': user_id,
        'customer_id': customer_info['id'],
        'subscription_id': customer_info['subscriptions']['data'][0]['id'],
        'subscribed': True,
        'modified_time': int(time.time())
    }

    response = customer_table.put_item(Item=data)
    if response['ResponseMetadata']['HTTPStatusCode'] == 200:
        return True
    else:
        return False


"""Cancel Subscription
"""


@app.route('/cancel', methods=['GET'])
@is_premium
@authenticated
def cancel_subscription():
    user_id = session['primary_identity']
    profile = get_profile(identity_id=user_id)
    try:
        if __delete_customer__(user_id) is False:
            return page_not_found('error')

        data = {
            'type': 'user',
            'id': user_id,
            'action': 'archive',
            'url': request.url,
            'email': profile.email
        }

        # publish cancel subscription message, archive user's file
        __publish_archive_status__(data)

        update_profile(identity_id=user_id, role='free_user')

        return render_template('home.html')
    except ClientError as e:
        print(e)
        return page_not_found(e)


'''
subscribe to premium plan
'''


@app.route('/subscribe', methods=['GET', 'POST'])
@authenticated
def subscribe():
    user_id = session['primary_identity']
    profile = get_profile(identity_id=user_id)

    if request.method == 'GET':
        if profile.role == 'premium_user':
            return render_template('subscribe_confirm.html')
        else:
            return render_template('subscribe.html')

    elif request.method == 'POST':

        # subscribe
        # https://pippinsplugins.com/stripe-integration-part-7-creating-and-storing-customers/

        stripe_token = request.form.get('stripe_token')
        try:
            stripe.api_key = app.config['STRIPE_SECRET_KEY']

            customer = stripe.Customer.create(
                email=profile.email,
                card=stripe_token,
                plan='premium_plan',
                description=user_id
            )
            # log the customer
            app.logger.info(customer)

            if __add_customer__(user_id, customer) is False:
                return page_not_found('error')

            # update database
            update_profile(identity_id=user_id, role='premium_user')

            data = {
                'type': 'user',
                'id': user_id,
                'action': 'restore',
                'url': request.url,
                'email': profile.email
            }

            # publish subscription message
            __publish_archive_status__(data)

            return render_template('subscribe_confirm.html')

        except ClientError as e:
            return page_not_found(e)
    else:
        return page_not_found('error')


"""DO NOT CHANGE CODE BELOW THIS LINE
*******************************************************************************
"""

"""Home page
"""
# Credit: Vas Vasiliadis <vas@uchicago.edu>


@app.route('/', methods=['GET'])
def home():
    return render_template('home.html')


"""Login page; send user to Globus Auth
"""


@app.route('/login', methods=['GET'])
def login():
    app.logger.info('Login attempted from IP {0}'.format(request.remote_addr))
    # If user requested a specific page, save it to session for redirect after authentication
    if (request.args.get('next')):
        session['next'] = request.args.get('next')
    return redirect(url_for('authcallback'))


"""404 error handler
"""


@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html',
      title='Page not found', alert_level='warning',
      message="The page you tried to reach does not exist. Please check the URL and try again."), 404


"""403 error handler
"""


@app.errorhandler(403)
def forbidden(e):
    return render_template('error.html',
      title='Not authorized', alert_level='danger',
      message="You are not authorized to access this page. If you think you deserve to be granted access, please contact the supreme leader of the mutating genome revolutionary party."), 403


"""405 error handler
"""


@app.errorhandler(405)
def not_allowed(e):
    return render_template('error.html',
      title='Not allowed', alert_level='warning',
      message="You attempted an operation that's not allowed; get your act together, hacker!"), 405


"""500 error handler
"""


@app.errorhandler(500)
def internal_error(error):
    return render_template('error.html',
      title='Server error', alert_level='danger',
      message="The server encountered an error and could not process your request."), 500

### EOF