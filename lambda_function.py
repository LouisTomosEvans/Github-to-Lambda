from cmath import log
from datetime import datetime, timedelta
from distutils.log import Log
import sys
import json
from instagrapi import Client
import boto3
import random
import email
import imaplib
import re
from requests.exceptions import ProxyError
from urllib3.exceptions import HTTPError
from instagrapi.exceptions import (
    ClientConnectionError,
    ClientForbiddenError,
    ClientLoginRequired,
    ClientThrottledError,
    GenericRequestError,
    PleaseWaitFewMinutes,
    RateLimitError,
    SentryBlock,
)
from instagrapi.exceptions import (
    BadPassword,
    ChallengeRequired,
    FeedbackRequired,
    LoginRequired,
    PleaseWaitFewMinutes,
    RecaptchaChallengeForm,
    ReloginAttemptExceeded,
    SelectContactPointRecoveryForm,
)

from instagrapi.mixins.challenge import ChallengeChoice


def next_proxy():
    dynamoclient = boto3.client('dynamodb')
    random_id = random.randint(1, 11)
    data = dynamoclient.get_item(
        TableName='proxies',
        Key={
            'id': {
                'S': str(random_id)
            }
        }
    )
    return data['Item']['proxy_url']['S']
    
def get_proxy(id):
    dynamoclient = boto3.client('dynamodb')
    data = dynamoclient.get_item(
        TableName='proxies',
        Key={
            'id': {
                'S': str(id)
            }
        }
    )
    return data['Item']['proxy_url']['S']

def get_user():
    dynamoclient = boto3.client('dynamodb')
    random_id = random.randint(10, 13)
    data = dynamoclient.get_item(
        TableName='instagram_creds',
        Key={
            'id': {
                'S': str(random_id)
            }
        }
    )
    print(data)

    if(data['Item']['Error']['S'] != ""):
        return get_user()
    elif(data['Item']['date']['S'] < datetime.now()):
        # delete error and date
        item = data['Item']
        data['Item']['Error']['S'] == ""
        data['Item']['date']['S'] == ""
        data = dynamoclient.put_item(
            TableName='instagram_creds',
            Item={item}
        )
        return [data['Item']['IG_Username']['S'], data['Item']['IG_Password']['S'], data['Item']['Email_Username']['S'], data['Item']['Email_Password']['S'], data['Item']['Preferred_Proxy']['S']]
    else:
        [data['Item']['IG_Username']['S'], data['Item']['IG_Password']['S'], data['Item']['Email_Username']['S'], data['Item']['Email_Password']['S'], data['Item']['Preferred_Proxy']['S'], data]


def Instagram_Get_User_Info(SEARCH_USERNAME, cl, retry_id):
    try:
        user = cl.user_info_by_username(SEARCH_USERNAME)
    except:
        dynamoclient = boto3.client('dynamodb')
        data = dynamoclient.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': retry_id
            },
            'response': {
                'S': "Error: Couldn't get user info!"
            }
        }
        )
        raise
    if(user.is_private == False):
        return user.pk
    else:
        dynamoclient = boto3.client('dynamodb')
        data = dynamoclient.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': retry_id
            },
            'response': {
                'S': 'Error: User is private!'
            },
            'Status': {
                'S': "Error"
            }
        }
        )

def Instagram_Get_User_Media(USER_ID, cl, num_posts, retry_id):
    try:
        medias = cl.user_medias_v1(USER_ID, int(num_posts))
    except:
        dynamoclient = boto3.client('dynamodb')
        data = dynamoclient.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': retry_id
            },
            'response': {
                'S': "Error: Couldn't get user's medias!"
            },
            'Status': {
                'S': "Error"
            }
        }
        )
    return medias

def get_code_from_email(username):
    mail = imaplib.IMAP4_SSL("imap.outlook.com")
    mail.login(Email_Username, Email_Password)
    mail.select("inbox")
    result, data = mail.search(None, "(UNSEEN)")
    assert result == "OK", "Error1 during get_code_from_email: %s" % result
    ids = data.pop().split()
    for num in reversed(ids):
        mail.store(num, "+FLAGS", "\\Seen")  # mark as read
        result, data = mail.fetch(num, "(RFC822)")
        assert result == "OK", "Error2 during get_code_from_email: %s" % result
        msg = email.message_from_string(data[0][1].decode())
        payloads = msg.get_payload()
        if not isinstance(payloads, list):
            payloads = [msg]
        code = None
        for payload in payloads:
            body = payload.get_payload(decode=True).decode()
            if "<div" not in body:
                continue
            match = re.search(">([^>]*?({u})[^<]*?)<".format(u=username), body)
            if not match:
                continue
            print("Match from email:", match.group(1))
            match = re.search(r">(\d{6})<", body)
            if not match:
                print('Skip this email, "code" not found')
                continue
            code = match.group(1)
            if code:
                return code
    return False


def challenge_code_handler(username, choice):
    #if choice == ChallengeChoice.SMS:
        #return get_code_from_sms(username)
    if choice == ChallengeChoice.EMAIL:
        return get_code_from_email(username)
    return False


def change_password_handler(username):
    # Simple way to generate a random string
    chars = list("abcdefghijklmnopqrstuvwxyz1234567890!&£@#")
    password = "".join(random.sample(chars, 10))
    return password

def on_error(e, time):
    dynamoclient = boto3.client('dynamodb')
    userItem = userObj['Item']
    userItem['Error'] = {'S': str(e)}
    userItem['date'] = {'S': str(datetime.now() + timedelta(minutes=time))}
    data = dynamoclient.put_item(
        TableName='instagram_creds',
        Item=userItem
    )


def handle_exception(client, e):
        dynamoclient = boto3.client('dynamodb')
        if isinstance(e, BadPassword):
            client.logger.exception(e)
            client.set_proxy(next_proxy())
            if client.relogin_attempt > 0:
                on_error(e, 7*24*60)
                raise ReloginAttemptExceeded(e)
            return client.update_client_settings(client.get_settings())
        elif isinstance(e, LoginRequired):
            client.logger.exception(e)
            client.relogin()
            return client.update_client_settings(client.get_settings())
        elif isinstance(e, ChallengeRequired):
            api_path = client.last_json.get("challenge", {}).get("api_path")
            if api_path == "/challenge/":
                client.set_proxy(next_proxy())
                client.settings = client.rebuild_client_settings()
            else:
                try:
                    client.challenge_resolve(client.last_json)
                except ChallengeRequired as e:
                    on_error(e, 2*24*60)
                    raise e
                except (ChallengeRequired, SelectContactPointRecoveryForm, RecaptchaChallengeForm) as e:
                    on_error(e, 4*24*60)
                    raise e
                #client.update_client_settings(client.get_settings())
                return True
        elif isinstance(e, FeedbackRequired):
            message = client.last_json["feedback_message"]
            if "This action was blocked. Please try again later" in message:
                on_error(e, 12*60)
            # client.settings = self.rebuild_client_settings()
            # return self.update_client_settings(client.get_settings())
            elif "We restrict certain activity to protect our community" in message:
                # 6 hours is not enough
                on_error(e, 7*12*60)
            elif "Your account has been temporarily blocked" in message:
                """
                    Based on previous use of this feature, your account has been temporarily
                    blocked from taking this action.
                    This block will expire on 2020-03-27.
                """
                on_error(e, )
        elif isinstance(e, PleaseWaitFewMinutes):
            on_error(e, 25)
        on_error(e, 36500*24*60)


def lambda_handler(event, context):

    global Email_Username
    global Email_Password
    global userObj

    ## Example Use Multi-Account (Max 100 requests a day to be safe)
    
    Search_Username = event['username']
    num_posts = event['num_posts']
    retry_id = event['retry_id']

    ## Example Use Multi-Proxy

    ## Create dynamoDB
    dynamoclient = boto3.client('dynamodb')

    ## Get User
    user = get_user()
    IG_Username = user[0]
    IG_Password = user[1]
    Email_Username = user[2]
    Email_Password = user[3]
    Preferred_Proxy = user[4]
    userObj = user[5]
    set_settings = True

    ## Login
    cl = Client(proxy=get_proxy(Preferred_Proxy))
    cl.set_locale('en_US')
    cl.set_timezone_offset(-7 * 60 * 60)  # Los Angeles UTC (GMT) -7 hours == -25200 seconds
    print(cl.get_settings())

    cl.handle_exception = handle_exception
    cl.challenge_code_handler = challenge_code_handler

    userItem = userObj['Item']

    if userItem['Settings']['S'] == "":
        set_settings = False
        userItem['Settings']['S'] = json.dumps(cl.get_settings(), indent = 4) 


    try:
        cl.login(IG_Username, IG_Password)
    except (ProxyError, HTTPError, GenericRequestError, ClientConnectionError):
        # Network level
        cl.set_proxy(next_proxy())
    except (SentryBlock, RateLimitError, ClientThrottledError):
        # Instagram limit level
        cl.set_proxy(next_proxy())
    except (ClientLoginRequired, PleaseWaitFewMinutes, ClientForbiddenError):
        # Logical level
        cl.set_proxy(next_proxy())

    
    if set_settings == True:
        cl.set_settings(json.loads(userItem['Settings']['S']))
    
    print(cl.get_settings())

    ##
    userItem = userObj['Item']
    userItem['Usage']['N'] = str(int(userItem['Usage']['N']) + 1)
    data = dynamoclient.put_item(
        TableName='instagram_creds',
        Item=userItem
    )

    ## Get Data
    UserID = Instagram_Get_User_Info(Search_Username, cl, retry_id)
    UserMedia = Instagram_Get_User_Media(UserID, cl, num_posts, retry_id)
    mediaList = []
    for media in UserMedia:
        if media.location is None:
            media.location = ""
        else:
            media.location = json.dumps(vars(media.location))
        if media.caption_text is None:
            media.caption_text = ""
        if media.thumbnail_url is None:
            media.thumbnail_url = ""

        data = dynamoclient.put_item(
        TableName='media',
        Item={
            'id': {
                'S': media.pk
            },
            'poll-id': {
                'S': retry_id
            },
            'type': {
                'N': str(media.media_type)
            },
            'location': {
                'S': media.location
            },
            'caption': {
                'S': media.caption_text
            },
            'thumbnail': {
                'S': media.thumbnail_url
            }
        }
        )
    
    data = dynamoclient.put_item(
    TableName='long-poll',
    Item={
        'id': {
            'S': retry_id
        },
        'UserID': {
            'S': UserID
        },
        'Status': {
            'S': "Completed"
        }
    }
    )