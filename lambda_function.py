from datetime import datetime, timedelta, timezone
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


def rebuild_client_settings(self, device=None):
    userItem = userObj['Item']
    client_settings = build_client_settings(self, device)
    #self.set_settings(json.loads(userItem['Settings']['S']))
    self.set_locale('en_US')
    self.set_timezone_offset(-7 * 60 * 60)
    self.set_settings(client_settings)
    userItem = userObj['Item']
    userItem['Settings']['S'] = json.dumps(self.get_settings(), indent = 4)
    dynamoclient = boto3.client('dynamodb')
    dynamoclient.put_item(
        TableName='instagram_creds',
        Item=userItem
    )
    return self.get_settings()

def build_client_settings(self, device=None):
    client_settings = self.get_settings()
    deviceObj = device_array[0]
    uaStr = user_agent_array[0]
    client_settings["device_settings"] = deviceObj
    client_settings["user_agent"] = uaStr
    return client_settings

def update_client_settings(self, settings):
    self.set_settings(settings)
    return True




def next_proxy():
    dynamoclient = boto3.client('dynamodb')
    random_id = random.randint(1, 10)
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
    random_id = random.randint(1, 50)
    data = dynamoclient.get_item(
        TableName='instagram_creds',
        Key={
            'id': {
                'S': str(random_id)
            }
        }
    )
    print(data)

    if(data['Item']['date']['S'] != ""):
        datetimeObj = datetime.strptime(data['Item']['date']['S'], '%Y-%m-%d %H:%M:%S.%f')
        if(datetimeObj < datetime.now()):
            # delete error and date
            item = data['Item']
            data['Item']['Error']['S'] == ""
            data['Item']['date']['S'] == ""
            res = dynamoclient.put_item(
                TableName='instagram_creds',
                Item=item
            )
            return [item['IG_Username']['S'], item['IG_Password']['S'], item['Email_Username']['S'], item['Email_Password']['S'], item['Preferred_Proxy']['S'], data]
        else:
            return get_user()
    else:
        return [data['Item']['IG_Username']['S'], data['Item']['IG_Password']['S'], data['Item']['Email_Username']['S'], data['Item']['Email_Password']['S'], data['Item']['Preferred_Proxy']['S'], data]


def Instagram_Get_User_Info(SEARCH_USERNAME, cl, retry_id):
    user = cl.user_info_by_username(SEARCH_USERNAME)
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
    medias = cl.user_medias_v1(USER_ID, int(num_posts))
    return medias

def get_code_from_email(username):
    mail = imaplib.IMAP4_SSL("imap.mail.ru")
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
            print('Bad Password')
            if client.relogin_attempt > 0:
                on_error(e, 7*24*60)
                raise ReloginAttemptExceeded(e)
            client.set_settings(rebuild_client_settings(client))
        elif isinstance(e, LoginRequired):
            client.logger.exception(e)
            print('Login Required')
            client.relogin()
            userObj['Item']['Settings']['S'] = json.dumps(client.get_settings(), indent = 4) 
            return
        elif isinstance(e, ChallengeRequired):
            api_path = client.last_json.get("challenge", {}).get("api_path")
            if api_path == "/challenge/":
                print('Challenge')
                #client.set_proxy(next_proxy())
                client.set_settings(rebuild_client_settings(client))
                client.login(IG_Username, IG_Password)
            else:
                try:
                    print('Challenge Resolve')
                    client.challenge_resolve(client.last_json)
                except ChallengeRequired as e:
                    on_error(e, 2*24*60)
                    raise e
                except (ChallengeRequired, SelectContactPointRecoveryForm, RecaptchaChallengeForm) as e:
                    on_error(e, 4*24*60)
                    raise e
                update_client_settings(client, client.get_settings())
                return True
        elif isinstance(e, FeedbackRequired):
            message = client.last_json["feedback_message"]
            if "This action was blocked. Please try again later" in message:
                on_error(e, 12*60)
                return
            # client.settings = self.rebuild_client_settings()
            # return self.update_client_settings(client.get_settings())
            elif "We restrict certain activity to protect our community" in message:
                # 6 hours is not enough
                on_error(e, 7*12*60)
                return
            elif "Your account has been temporarily blocked" in message:
                """
                    Based on previous use of this feature, your account has been temporarily
                    blocked from taking this action.
                    This block will expire on 2020-03-27.
                """
                on_error(e, )
                return
        elif isinstance(e, PleaseWaitFewMinutes):
            on_error(e, 25)
            return
        on_error(e, 36500*24*60)


def lambda_handler(event, context):

    global Email_Username
    global Email_Password
    global IG_Username
    global IG_Password
    global userObj
    global device_array
    global user_agent_array

    device_array = [{
      "cpu": "h1",
      "dpi": "640dpi",
      "model": "h1",
      "device": "RS988",
      "resolution": "1440x2392",
      "app_version": "117.0.0.28.123",
      "manufacturer": "LGE/lge",
      "version_code": "168361634",
      "android_release": "6.0.1",
      "android_version": 23
    }]
    user_agent_array = ["Instagram 117.0.0.28.123 Android (23/6.0.1; 640dpi; 1440x2392; LGE/lge; h1; RS988; h1; en_US; 168361634)"]

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

    if set_settings == True:
        cl.set_settings(json.loads(userItem['Settings']['S']))

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

    userItem['Settings']['S'] = json.dumps(cl.get_settings(), indent = 4) 

    ## Get Data
    UserID = Instagram_Get_User_Info(Search_Username, cl, retry_id)
    UserMedia = Instagram_Get_User_Media(UserID, cl, num_posts, retry_id)

    ##
    userItem['Usage']['N'] = str(int(userItem['Usage']['N']) + 1)
    data = dynamoclient.put_item(
        TableName='instagram_creds',
        Item=userItem
    )
                                                                                                                                
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

        dt_epoch = datetime(1970, 1, 1)
        dt_epoch = dt_epoch.replace(tzinfo=timezone.utc)
        epoch = (media.taken_at - dt_epoch).total_seconds()

        data = dynamoclient.put_item(
        TableName='media',
        Item={
            'id': {
                'S': media.pk + "_" + retry_id
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
            }, 
            'code': {
                'S': media.code
            }, 
            'date': {
                'S': str(epoch)
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