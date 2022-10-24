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
                'S': '1'
            },
            'response': {
                'S': "Error: Couldn't get user info!"
            }
        }
        )
    if(user.is_private == False):
        return user.pk
    else:
        data = client.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': '1'
            },
            'response': {
                'S': 'Error: User is private!'
            },
            'Status': {
                'S': "Error"
            }
        }
        )

def Instagram_Get_User_Media(USER_ID, cl, num_posts):
    try:
        medias = cl.user_medias_v1(USER_ID, num_posts)
    except:
        data = client.put_item(
        TableName='long-poll',
        Item={
            'id': {
                'S': '1'
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


def lambda_handler(event, context):

    ## Example Use Multi-Account (Max 100 requests a day to be safe)
    IG_Username = 'louistomosevans'
    IG_Password = 'mtYm49bxbjvKZTy'
    
    Search_Username = event['username']
    num_posts = event['num_posts']

    ## Example Use Multi-Proxy

    ## Create dynamoDB
    client = boto3.client('dynamodb')

    ## Login
    cl = Client()
    cl.login(IG_Username, IG_Password)

    ## Get Data
    UserID = Instagram_Get_User_Info(Search_Username, cl)
    UserMedia = Instagram_Get_User_Media(UserID, cl, num_posts)
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

        data = client.put_item(
        TableName='media',
        Item={
            'id': {
                'S': media.pk
            },
            'poll-id': {
                'S': '1'
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
    
    data = client.put_item(
    TableName='long-poll',
    Item={
        'id': {
            'S': '1'
        },
        'UserID': {
            'S': UserID
        },
        'Status': {
            'S': "Completed"
        }
    }
    )