import sys
import json
from instagrapi import Client
from instagrapi.types import StoryMention, StoryMedia, StoryLink, StoryHashtag

def Instagram_Get_User_Info(SEARCH_USERNAME):
    # Use a breakpoint in the code line below to debug your script.
    user = cl.user_info_by_username(SEARCH_USERNAME)
    if(user.is_private == False):
        return user.pk
    else:
        sys.exit("Error: User is Private!")

def Instagram_Get_User_Media(USER_ID):
    # Use a breakpoint in the code line below to debug your script.
    medias = cl.user_medias_v1(USER_ID)
    return medias


def lambda_handler(event, context):

    ## Example Use Multi-Account (Max 100 requests a day to be safe)
    IG_Username = 'louistomosevans'
    IG_Password = 'mtYm49bxbjvKZTy'
    Search_Username = 'alacrityfoundationuk'

    ## Example Use Multi-Proxy

    cl = Client()
    cl.login(IG_Username, IG_Password)
    UserID = Instagram_Get_User_Info(Search_Username)
    UserMedia = Instagram_Get_User_Media(UserID)
    mediaList = []
    for media in UserMedia:
        mediaList.append(media.__dict__)

    print(json.dumps(mediaList, sort_keys=True, default=str))
