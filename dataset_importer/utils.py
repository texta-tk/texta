import requests
import os
import re
import time
import shutil

def download(url, target_directory, chunk_size=1024):
    response = requests.get(url, stream=True)

    file_name = _derive_file_name(response, url)

    with open(os.path.join(target_directory, file_name), 'wb') as downloaded_file:
        for chunk in response.iter_content(chunk_size=chunk_size):
            if chunk:
                downloaded_file.write(chunk)


def prepare_import_directory(importer_directory):
    temp_folder_name = str(int(time.time()*1000000))
    temp_folder_path = os.path.join(importer_directory, temp_folder_name)
    os.makedirs(temp_folder_path)

    return temp_folder_path


def tear_down_import_directory(import_directory_path):
    shutil.rmtree(import_directory_path)


def _derive_file_name(response, url):
    file_name = ''

    if 'content-disposition' in response:
        file_names = re.findall('filename=(.*)', response['content-disposition'])

        if file_names:
            file_name = file_names[0].strip('\'" ')

    if not file_name:
        file_name = os.path.basename(url)

    return file_name

