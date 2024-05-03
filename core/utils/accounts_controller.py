from ..models import AccountData, AccountCredentials, OauthData, ProfileData, AccountSettings, Filter, TimeDiapason
from .time_formater import str_to_timesec
import json, os


class AccountsController:
    def __init__(self, folder):
        self.folder = folder
 
    def get_accounts(self) -> list[AccountData]:
        accounts = []

        for filename in os.listdir(self.folder):
            if filename.endswith('.json'):
                with open(f'{self.folder}/{filename}', 'r', encoding='utf-8') as file:
                    account_data = json.load(file)
                    accounts.append(
                        AccountData(
                            AccountCredentials(account_data['email'], account_data['password']),
                            OauthData(account_data['accessToken'], account_data['refreshToken']),
                            ProfileData(account_data['phone'], account_data['name']),
                            AccountSettings(account_data['actionsTimeout'], account_data['randomTimeout'], [TimeDiapason(*str_to_timesec(str_time)) for str_time in account_data['workTime']]),
                            Filter(
                                account_data['days'],
                                [TimeDiapason(*str_to_timesec(str_time)) for str_time in account_data['slotsIntervals']],
                                account_data['messagesSending1'],
                                account_data['chatID1'],
                                account_data['messagesSending2'],
                                account_data['chatID2'],
                                account_data['zone']
                            )
                        )
                    )
        return accounts
        
    def update_account(self, account: AccountData):
        filename = account.credentials.email.split('@')[0]
        with open(f'{self.folder}/{filename}.json', 'r+', encoding='utf-8') as file:
            data = json.load(file)

            data['accessToken'] = account.oauth.access_token
            data['refreshToken'] = account.oauth.refresh_token
            data['name'] = account.profile.name
            data['phone'] = account.profile.phone

            file.seek(0)
            json.dump(data, file, indent=4, ensure_ascii=False)
