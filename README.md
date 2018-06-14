
## Capstone Project: Genomic Annotation Service (GAS)
## Student: Honglei Zhou

## About the Genomic Annotation Service (GAS) project
This is a fully functional software­-as­-a­-service for genomics annotation. GAS makes use of various clouds services running on Amazon Web Services. It has the capabilities of auto scaling based on usage and is integrated with stripe for payments processing.

## Functionalities
### Annotate user file 
GAS provides service to annotate user's uploaded files and notify user when job is done. User can download the result when the job finish.

### Archive Free user data to Glacier
Our policy for the GAS is that Free users can only download their data for up to 30 minutes after completion of their annotation job. After that, their results data will be archived to a Glacier vault. This allows us to retain their data at relatively low cost, and to restore it in the event that the user decides to upgrade to a Premium user.

### Enable Free users to upgrade to Premium via Stripe payments
Our GAS application uses a subscription model whereby Premium users can pay $XXX per week to run as many analyses as they want and store as much data as they want. The Stripe service (www.stripe.com) is integrated to manage all subscription and billing functions for the GAS.

### Restore data for users that upgrade to Premium
When a Free user converts to a Premium user, move all of that user’s results files from the Glacier vault back to the s3 buckets.

### Scalability
GAS will automatically scale out/in the nodes based on requests and submitted jobs.

### Directories and Files:
1. [anntools](https://github.com/mpcs-cc/cp-zhouatuchicago/tree/master/anntools): contains annotator.py, config_init.py, run.py, utils.cfg, run_annotator.sh
2. [utils](https://github.com/mpcs-cc/cp-zhouatuchicago/tree/master/utils): contains archive_restore.py, config_init.py, results_archive.py, results_notify.py, run_utils.sh, utils.cfg
3. [gas](https://github.com/mpcs-cc/cp-zhouatuchicago/tree/master/gas): contains templates, environment variables and scripts for web server.
4. [zipfiles](https://github.com/mpcs-cc/cp-zhouatuchicago/tree/master/zipfiles): contains zip files for auto scaling groups.
5. [auto_scaling_user_data_annotator.txt](https://github.com/mpcs-cc/cp-zhouatuchicago/blob/master/auto_scaling_user_data_annotator.txt): user data for initiate annotator when launching instances.
6. [auto_scaling_user_data_web_server.txt](https://github.com/mpcs-cc/cp-zhouatuchicago/blob/master/auto_scaling_user_data_web_server.txt): user data for initiate web server when launching instances.
7. [auto_scaling_user_data_utils.txt](https://github.com/mpcs-cc/cp-zhouatuchicago/blob/master/auto_scaling_user_data_utils.txt): user data for initiate utils when launching instances.
8. [test_annotator_farm.py](https://github.com/mpcs-cc/cp-zhouatuchicago/blob/master/test_annotator_farm.py): script used to test annotator farm.
9. [load testing exercise.pdf](https://github.com/mpcs-cc/cp-zhouatuchicago/blob/master/load%20testing%20exercise.pdf): load testing exercise results.

### References:
1. https://stackoverflow.com/questions/3717793/javascript-file-upload-size-validation
2. http://boto3.readthedocs.io/en/latest/guide/sqs.html
3. http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Bucket.download_file
4. https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
5. http://boto3.readthedocs.io/en/latest/guide/dynamodb.html#getting-an-item
6. https://docs.python.org/3/library/datetime.html
7. https://www.w3schools.com/html/html_lists.asp
8. https://www.w3schools.com/tags/att_table_rules.asp
9. http://boto3.readthedocs.io/en/latest/reference/services/s3.html#S3.Object.get
10. https://stackoverflow.com/questions/31976273/open-s3-object-as-a-string-with-boto3
11. http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
12. https://github.com/santoshghimire/boto3-examples/blob/master/dynamodb.py
13. https://stripe.com/docs/api#delete_account
14. https://pippinsplugins.com/stripe-integration-part-7-creating-and-storing-customers/
15. https://www.blog.pythonlibrary.org/2013/10/25/python-101-an-intro-to-configparser/
16. http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
17. http://boto3.readthedocs.io/en/latest/reference/services/glacier.html#Glacier.Client.initiate_job
18. http://boto3.readthedocs.io/en/latest/reference/services/sns.html#SNS.Topic.publish
19. http://boto3.readthedocs.io/en/latest/guide/sqs.html
20. http://boto3.readthedocs.io/en/latest/reference/services/s3.html#bucket
