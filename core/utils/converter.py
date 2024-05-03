import json


try:
    accounts_path = input('Расположение файла с аккаунтами: ')
    accounts_txt = open(accounts_path)
    accounts_creditails = []
    for account_line in accounts_txt.read().splitlines():
        accounts_creditails.append(account_line.split(':'))
    
    for account_creditails in accounts_creditails:
        email, password = account_creditails
        filename = email.split('@')[0]

        with open(f'data/{filename}.json', 'w', encoding='utf-8') as file:
            account_data = {
                'accessToken': None,
                'refreshToken': None,
                'name': None,
                'phone': None,
                'email': email,
                'password': password,
                'actionsTimeout': 1.5,
                'randomTimeout': [1.0, 3.5],
                'days': [
                    'Понедельник', 
                    'Вторник', 
                    'Среда', 
                    'Четверг', 
                    'Пятница', 
                    'Суббота', 
                    'Воскресенье'
                ],
                'slotsIntervals': [
                    '00.00-24.00'
                ],
                'messagesSending1': "yes",
                'chatID1': None,
                'messagesSending2': "no",
                'chatID2': None,
                'zone': 'Ukraine',

                'workTime': [
                    '00.00-24.00'
                ]
            }

            json.dump(account_data, file, indent=4, ensure_ascii=False)
    
    print(f'Загружено учетных записей: {len(accounts_creditails)}')
except TypeError:
    print(f'Неверный формат аккаунта: {account_line}')
except FileNotFoundError:
    print('Не удалось найти файл с аккаунтами')



