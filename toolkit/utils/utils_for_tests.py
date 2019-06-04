from django.contrib.auth.models import User
from termcolor import colored


def create_test_user(name: str='tester', email: str='test@mail.com', password: str='password'):
    '''Creates an User for Testing'''
    user = User.objects.create(username=name, email=email)
    user.set_password(password)
    user.save()
    return user

def print_output(test_name, data,  main_color: str='magenta', output_color: str='yellow', main_attrs=['bold'], output_attrs=[]):
    main_string = f'\n\nTEST  "{test_name}" OUTPUT:'
    data_string = f'{data}\n\n'
    print(colored(main_string, main_color, attrs=main_attrs))
    print(colored(data_string, output_color, attrs=output_attrs))
