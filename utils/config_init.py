import configparser
import os

basedir = os.path.abspath(os.path.dirname(__file__))


# ref: https://www.blog.pythonlibrary.org/2013/10/25/python-101-an-intro-to-configparser/
class UtilsConfig(object):

    def __init__(self):

        self.config = configparser.ConfigParser()
        self.config.read('utils.cfg')
        self.AWS_REGION_NAME = self.config['AWS']['AWS_REGION_NAME']

        self.AWS_S3_INPUTS_BUCKET = self.config['AWS']['AWS_S3_INPUTS_BUCKET']
        self.AWS_S3_RESULTS_BUCKET = self.config['AWS']['AWS_S3_RESULTS_BUCKET']

        # Set the S3 key (object name) prefix to your CNetID
        # Keep the trailing '/' if using my upload code in views.py
        self.AWS_S3_KEY_PREFIX = self.config['AWS']['AWS_S3_KEY_PREFIX']
        self.AWS_GLACIER_VAULT = self.config['AWS']['AWS_GLACIER_VAULT']

        # Change the ARNs below to reflect your SNS topics
        self.AWS_SNS_JOB_REQUEST_TOPIC = self.config['AWS']['AWS_SNS_JOB_REQUEST_TOPIC']
        self.AWS_SNS_JOB_COMPLETE_TOPIC = self.config['AWS']['AWS_SNS_JOB_COMPLETE_TOPIC']
        self.AWS_SNS_JOB_ARCHIVE_TOPIC = self.config['AWS']['AWS_SNS_JOB_ARCHIVE_TOPIC']
        self.AWS_SNS_JOB_RESTORE_TOPIC = self.config['AWS']['AWS_SNS_JOB_RESTORE_TOPIC']

        # SQS Name
        self.AWS_SQS_JOB_REQUEST_NAME = self.config['AWS']['AWS_SQS_JOB_REQUEST_NAME']
        self.AWS_SQS_JOB_COMPLETE_NAME = self.config['AWS']['AWS_SQS_JOB_COMPLETE_NAME']
        self.AWS_SQS_JOB_ARCHIVE_NAME = self.config['AWS']['AWS_SQS_JOB_ARCHIVE_NAME']
        self.AWS_SQS_JOB_RESTORE_NAME = self.config['AWS']['AWS_SQS_JOB_RESTORE_NAME']

        # Change the table name to your own
        self.AWS_DYNAMODB_ANNOTATIONS_TABLE = self.config['AWS']['AWS_DYNAMODB_ANNOTATIONS_TABLE']

        # Change the email address to your username
        self.MAIL_DEFAULT_SENDER = self.config['GASAPP']['MAIL_DEFAULT_SENDER']

        # time before free user results are archived (in seconds)
        self.FREE_USER_DATA_RETENTION = int(self.config['GASAPP']['FREE_USER_DATA_RETENTION'])
        self.FREE_USER_FILE_LIMIT = int(self.config['GASAPP']['FREE_USER_FILE_LIMIT'])

        self.LOCAL_DATA_PREFIX = self.config['GASAPP']['LOCAL_DATA_PREFIX']
