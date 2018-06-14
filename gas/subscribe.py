"""Subscription management handler
"""

import stripe
import time
import boto3

from flask import (abort, flash, redirect, render_template,
  request, session, url_for)

from gas import app, db
from decorators import authenticated, is_premium
from auth import get_profile, update_profile
from botocore.exceptions import ClientError


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