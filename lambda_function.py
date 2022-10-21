import sys
import json
from instagrapi import Client
from instagrapi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag
import boto3

def Instagram_Get_User_Info(SEARCH_USERNAME, cl):
    try:
        user = cl.user_info_by_username(SEARCH_USERNAME)
    except:
        data = client.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': retryID
            },
            'response': {
                'S': "Error: Couldn't get user info!"
            }
        }
        )
    if(user.is_private == False):
        return user.pk
    else{
        data = client.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': retryID
            },
            'response': {
                'S': 'Error: User is private!'
            }
        }
        )
    }

def Instagram_Get_User_Media(USER_ID, cl):
    try:
        medias = cl.user_medias_v1(USER_ID)
    except:
        data = client.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': retryID
            },
            'response': {
                'S': "Error: Couldn't get user's medias!"
            }
        }
        )
    return medias


def lambda_handler(event, context):

    ## Example Use Multi-Account (Max 100 requests a day to be safe)
    IG_Username = 'louistomosevans'
    IG_Password = 'mtYm49bxbjvKZTy'
    Search_Username = 'alacrityfoundationuk'

    ## Example Use Multi-Proxy

    ## Create dynamoDB
    client = boto3.client('dynamodb')

    ## Login
    cl = Client()
    cl.login(IG_Username, IG_Password)

    ## Get Data
    UserID = Instagram_Get_User_Info(Search_Username, cl)
    UserMedia = Instagram_Get_User_Media(UserID, cl)
    mediaList = []
    for media in UserMedia:
        mediaList.append(media.__dict__)
    
    data = client.put_item(
    TableName='long-poll',
    Item={
        'id': {
            'S': retryID
        },
        'response': {
            'S': json.dumps(mediaList, sort_keys=True, default=str)
        }
    }
    )
