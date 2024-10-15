'''
    gbapi - Gameboard API class

    implemented is the v1 API version

    @author: Pim van Stam
    @copyright: S3group, 2024
    @since: 11-09-2024
    @version: 1.0
    

'''
import requests
import json

api_version = "/v1"


class GameboardApi(object):
    '''
    classdocs
    '''

    def __init__(self, base_url=None, login=None, password=None):
        self.base_url = base_url
        self.login = login
        self.password = password
        self.accesstoken = None
        self.refreshtoken = None
        self.accesstoken_timeout = None
        self.refreshtoken_timeout = None
        # https methods
        self.GET=requests.get
        self.DELETE=requests.delete
        self.POST=requests.post
        self.PUT=requests.put
        

    def authenticate(self, login=None, password=None):
        '''
            Get oauth2 refresh and initial access token
        '''
        if login != None:
            self.login = login
        if password != None:
            self.password = password

        header_data = { "Content-Type": "application/x-www-form-urlencoded",
                        "User-Agent": "gbapi-client/1.0"}

        data = { "grant_type": "password",
                 "username": self.login,
                 "login": self.login,
                 "password": self.password}
        
        retval = requests.post(self.base_url + "/authentication", headers=header_data, data=data,
                               verify=True)
        
        if retval.status_code != 200:
            return (0, f"{retval.status_code}: {retval.text}")
        
        self.accesstoken = json.loads(retval.content)["access_token"]
        return (1, self.accesstoken)
        

    def __send_data(self, url, method=None, data=""):
        '''
            Send data from a given sub url with the retrieved access token.
            The access token must be requested first.
        '''
#        header_data = { "Accept" : "application/json",
        header_data = { "Accept": "*/*",
                        "User-Agent": "gbapi-client/1.0",
                        "Authorization": "Bearer " + self.accesstoken
                      }

        if method == None:
            return None
        
        json_data = json.dumps(data)
        retval = method(self.base_url + api_version + url, headers=header_data, data=json_data)

        if retval.status_code != 200:
            return (0, f"{retval.status_code}: {retval.text}")

        return (1, retval.content)



    def get_data(self, url, data=""):
        return self.__send_data(url, self.GET, data)

    def delete_data(self, url, data=""):
        return self.__send_data(url, self.DELETE, data)

    def post_data(self, url, data=""):
        return self.__send_data(url, self.POST, data)

    def put_data(self, url, data=""):
        return self.__send_data(url, self.PUT, data)


    # DDoS tests
    def get_ddostests(self, test_id=None):
        if test_id == None:
            return self.get_data("/ddostests")
        else:
            return self.get_data(f"/ddostests/{test_id}")

    def get_ddostests_targets(self, test_id):
        return self.get_data(f"/ddostests/{test_id}/targets")


    # Targets methods
    def get_targets(self, target_id=None):
        if target_id == None:
            return self.get_data("/targets")
        else:
            return self.get_data(f"/targets/{target_id}")

    def get_targets_measurementtype(self, target_id):
        return self.get_data(f"/targets/{target_id}/measurementtype")
    
    def post_target_state(self, target_id, target_state):
        return self.post_data(f"/targets/{target_id}/state/{target_state}")


    # Measurement types
    def get_measurementtypes(self, type_id=None):
        if type_id == None:
            return self.get_data("/measurementtypes")
        else:
            return self.get_data(f"/measurementtypes/{type_id}")

    def get_measurementtypes_nodelist(self, type_id):
        return self.get_data(f"/measurementtypes/{type_id}/nodelist")


    # Node lists
    def get_nodelists(self, list_id=None):
        if list_id == None:
            return self.get_data("/nodelists")
        else:
            return self.get_data(f"/nodelists/{list_id}")

    def put_nodelist(self, list_id=1, nodelist=[]):
#        return self.put_data(f"/nodelists/{list_id}", nodelist)
        return self.put_data(f"/nodelists", nodelist)        

