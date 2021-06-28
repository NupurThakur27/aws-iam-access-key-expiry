import json
import boto3
import base64
import datetime
import os
from datetime import datetime
from datetime import timedelta
from botocore.exceptions import ClientError

AWS_EMAIL_REGION = 'ap-southeast-1'

KEY_YOUNG_MESSAGE = 'Key is still young'
KEY_DEACTIVATED_MESSAGE = 'key is now EXPIRED! Changing key to INACTIVE state'
KEY_DELETED_MESSAGE = 'Key is now deleted'

MASK_ACCESS_KEY_LENGTH = 15
ACCESS_KEY_LENGTH = 20
KEY_STATE_ACTIVE = "Active"
KEY_STATE_INACTIVE = "Inactive"

KEY_MAX_DEACTIVATE_AGE_IN_DAYS = 45
KEY_MAX_DELETE_AGE_IN_DAYS = 60

    
def mask_access_key(access_key):
    return access_key[-(ACCESS_KEY_LENGTH-MASK_ACCESS_KEY_LENGTH):].rjust(len(access_key), "*")
    
def key_age(key_created_date):
    tz_info = key_created_date.tzinfo
    age = datetime.now(tz_info) - key_created_date

    print ('key age %s' % age)

    key_age_str = str(age)
    if 'days' not in key_age_str:
        return 0

    days = int(key_age_str.split(',')[0].split(' ')[0])

    return days

def send_deactivate_email(username, age, access_key_id):
    DELETION_DATE=datetime.today() + timedelta(15)
    emailmsg = """The Access Key [%s] belonging to User [%s] has been automatically deactivated due to it being %s days old.
    
Please generate another access key for yourself otherwise the existing Access Key will be deleted after 15 days [%s]""" % (access_key_id, username, age,DELETION_DATE.strftime("%d %b %Y, %A"))
    emailSubject = 'AWS IAM Access Key Rotation - Deactivation of Access Key: %s' % access_key_id
    ops_sns_topic ='arn:aws:sns:ap-southeast-1:325903710924:key-rotation'
    sns_send_report = boto3.client('sns',region_name=AWS_EMAIL_REGION)
    sns_send_report.publish(TopicArn=ops_sns_topic, Message=emailmsg, Subject=emailSubject)

def send_delete_email(username, age, access_key_id):
    emailmsg = 'The Access Key [%s] belonging to User [%s] has been automatically ' \
           'deleted due to it being %s days old' % (access_key_id, username, age)
    emailSubject = 'AWS IAM Access Key Rotation - Deletion of Access Key: %s' % access_key_id
    ops_sns_topic ='arn:aws:sns:ap-southeast-1:325903710924:key-rotation'
    sns_send_report = boto3.client('sns',region_name=AWS_EMAIL_REGION)
    sns_send_report.publish(TopicArn=ops_sns_topic, Message=emailmsg, Subject=emailSubject)

def deactive_key(uname):
    try:
        username=uname
        client = boto3.client('iam')
        access_keys = client.list_access_keys(UserName=username)['AccessKeyMetadata']
        user_keys = []

        for access_key in access_keys:
            access_key_id = access_key['AccessKeyId']
            masked_access_key_id = mask_access_key(access_key_id)
            print ('AccessKeyId %s' % masked_access_key_id)
            existing_key_status = access_key['Status']
            print (existing_key_status)
            key_created_date = access_key['CreateDate']
            print ('key_created_date %s' % key_created_date)
            age = key_age(key_created_date)
            print ('age %s' % age)

            key_state = ''
            key_state_changed = False
            if age < KEY_MAX_DEACTIVATE_AGE_IN_DAYS:
                key_state = KEY_YOUNG_MESSAGE
            elif age >= KEY_MAX_DEACTIVATE_AGE_IN_DAYS:
                key_state = KEY_DEACTIVATED_MESSAGE
                client.update_access_key(UserName=username, AccessKeyId=access_key_id, Status=KEY_STATE_INACTIVE)
                send_deactivate_email(username, age, masked_access_key_id)
                key_state_changed = True
                key_info = {'accesskeyid': masked_access_key_id, 'age': age, 'state': key_state, 'changed': key_state_changed}
                user_keys.append(key_info)   
        status = {'username': username, 'keys': user_keys}         
        return status 
    except ClientError as e:
        print (e)

def delete_key(uname):
    try:
        username=uname
        client = boto3.client('iam')
        access_keys = client.list_access_keys(UserName=username)['AccessKeyMetadata']
        user_keys = []

        for access_key in access_keys:
            access_key_id = access_key['AccessKeyId']

            masked_access_key_id = mask_access_key(access_key_id)

            print ('AccessKeyId %s' % masked_access_key_id)

            existing_key_status = access_key['Status']
            print (existing_key_status)

            key_created_date = access_key['CreateDate']
            print ('key_created_date %s' % key_created_date)

            age = key_age(key_created_date)
            print ('age %s' % age)
            key_state = ''
            key_state_changed = False
            if age < KEY_MAX_DELETE_AGE_IN_DAYS:
                key_state = KEY_YOUNG_MESSAGE
            elif age >= KEY_MAX_DELETE_AGE_IN_DAYS:
                key_state = KEY_DELETED_MESSAGE
                if existing_key_status == KEY_STATE_ACTIVE:
                    client.update_access_key(UserName=username, AccessKeyId=access_key_id, Status=KEY_STATE_INACTIVE)
                iam.delete_access_key (UserName=username,AccessKeyId=access_key_id)
                send_delete_email(username, age, masked_access_key_id)
                key_state_changed = True
            key_info = {'accesskeyid': masked_access_key_id, 'age': age, 'state': key_state, 'changed': key_state_changed}
            user_keys.append(key_info)   
        status = {'username': username, 'keys': user_keys}         
        return status            

    except ClientError as e:
        print (e)
    
def lambda_handler(event, context):
    # TODO implement
    faction=event ["action"]
    fuser_name=event ["username"]
    if faction == "deactivate":
        status = deactive_key(fuser_name)
        print (status)
    elif faction == "delete":
        status = delete_key(fuser_name)
        print (status)
