from httpx import AsyncClient
from datetime import datetime
from ..models import OauthData, SlotData, ProfileData, AccountCredentials
from ..exceptions import GlovoError, AccessTokenError, InvalidCredentials, SlotTakeError, AccountBlocked
from ..utils import ts_to_timesec
import uuid


class GlovoCourier:
    def __init__(
            self, 
            http_сlient: AsyncClient,
            credentials: AccountCredentials,
            oauth: OauthData
        ) -> None:

        self.http_сlient = http_сlient
        self.credentials = credentials
        self.oauth = oauth

        self.__set_headers()

    def __set_headers(self):
        self.http_сlient.headers = {
            'glovo-app-platform': 'Android',
            'glovo-app-version': '2.2013.0',
            'glovo-api-version': '8',
            'glovo-app-type': 'courier',
            'glovo-app-development-state': 'Production',
            'glovo-os-version': '7.1.2',
            'glovo-language-code': 'ru',
            'user-agent': 'Glover/2.213.0 (Linux; Android 13) AppleWebKit/537.36 (KHTML, like Gecko) okhttp/4.9.3 SDK/25',
            'glovo-dynamic-session-id': str(uuid.uuid4()),
            'glovo-device-id': '',
            'content-type': 'application/json; charset=UTF-8'
        }

    async def auth(self) -> OauthData:
        response = await self.http_сlient.post(
            'https://api.glovoapp.com/oauth/token',

            json = {
                'grantType': 'password',
                'password': self.credentials.password,
                'termsAndConditionsChecked': False,
                'userType': 'courier',
                'username': self.credentials.email
            }
        )
        response_data = response.json()
#        print(f'auth: [{response.status_code}]')
        if response.status_code == 401:
            raise InvalidCredentials(response_data['error']['message'])
        self.oauth = OauthData(response_data['accessToken'], response_data['refreshToken'])
        return self.oauth
    
    async def refresh(self) -> OauthData:
        response = await self.http_сlient.post('https://api.glovoapp.com/oauth/refresh', json = {'refreshToken': self.oauth.refresh_token})
#        print(f'response: [{response.status_code}]')
        response_data = response.json()
        if response.status_code == 401:
            return await self.auth()

        self.oauth = OauthData(response_data['accessToken'], response_data['refreshToken'])
        return self.oauth
    

    async def get_slots(self) -> list[SlotData]:
        response = await self.http_сlient.get('https://api.glovoapp.com/v4/scheduling/calendar', headers = {'authorization': self.oauth.access_token})
        response_data = response.json()
#        print(f'get_slots: [{response.status_code}]')
        if response.status_code == 401:
            raise AccessTokenError(response_data['error']['message'])
        elif response.status_code == 400:
            raise GlovoError(response_data['error']['message'])
        elif response.status_code == 429:
            raise AccountBlocked(response_data['error']['message'])
        elif response.status_code == 410:
            raise GlovoError('User agent is old')
        elif response.is_error:
            raise GlovoError(response_data['error']['message'])
        else:
            data = []
            for day in response_data['days']:
                for zone in day['zonesSchedule']:
                    for slot in zone['slots']:
                        weekday_ts: int = day['date']
                        start_ts: int = slot['startTime']
                        end_ts: int = slot['endTime']
                        weekday = datetime.utcfromtimestamp(weekday_ts).strftime('%A').capitalize()
                        slot_id = slot['id'] 
                        status = slot['status'] 

                        data.append(SlotData(slot_id, weekday, weekday_ts, start_ts, end_ts, True if status == 'BOOKED' else False))
            
            return data

    async def get_free_slots(self) -> list[SlotData]:
        response = await self.http_сlient.get('https://api.glovoapp.com/v4/scheduling/calendar', headers = {'authorization': self.oauth.access_token})
        response_data = response.json()
#        print(f'get_free_slots: [{response.status_code}]')
        if response.status_code == 401:
            raise AccessTokenError(response_data['error']['message'])
        elif response.status_code == 400:
            raise GlovoError(response_data['error']['message'])
        elif response.status_code == 429:
            raise AccountBlocked(response_data['error']['message'])
        elif response.status_code == 410:
            raise GlovoError('User agent is old')
        elif response.is_error:
            raise GlovoError(response_data['error']['message'])
        else:
            days: list = response_data['days']
            data = []

            for day in days:
                for zone in day['zonesSchedule']:
                    slots: list = zone['slots']    
                    for slot in slots:
                        weekday_ts: int = day['date']
                        start_ts: int = slot['startTime']
                        end_ts: int = slot['endTime']
                        weekday = datetime.utcfromtimestamp(weekday_ts / 1000).strftime('%A').capitalize()
                        slot_id = slot['id'] 
                        status = slot['status'] 

                        if status == 'AVAILABLE':
                            data.append(SlotData(slot_id, weekday, weekday_ts, start_ts, end_ts, False))
            
            return data


    async def book_slot(self, slot_id: int) -> bool:
        response = await self.http_сlient.put(
            f'https://api.glovoapp.com/v4/scheduling/slots/{slot_id}', 

            headers = {'authorization': self.oauth.access_token},
            json = {
                'booked': True,
                'storeAddressId': None
            }
        )
        response_data = response.json()

        if response.status_code == 401:
            raise AccessTokenError(response_data['error']['message'])
        elif response.status_code == 400:
            raise SlotTakeError(response_data['error']['message'])
        elif response.status_code == 429:
            raise AccountBlocked(response_data['error']['message'])
        elif response.status_code == 410:
            raise GlovoError('User agent is old')
        elif response.is_error:
            raise GlovoError(response_data['error']['message'])
        else:
            return True
        
    async def profile(self) -> ProfileData:
        response = await self.http_сlient.get('https://api.glovoapp.com/v3/couriers/profile/personal_info', headers = {'authorization': self.oauth.access_token})
        response_data = response.json()

        if response.status_code == 401:
            raise AccessTokenError(response_data['error']['message'])
        elif response.status_code == 400:
            raise GlovoError(response_data['error']['message'])
        elif response.status_code == 429:
            raise AccountBlocked(response_data['error']['message'])
        elif response.status_code == 410:
            raise GlovoError('User agent is old')
        elif response.is_error:
            raise GlovoError(response_data['error']['message'])
        else:
            name = response_data['header']['name']
            phone = response_data['header']['phone']

            return ProfileData(phone, name)


