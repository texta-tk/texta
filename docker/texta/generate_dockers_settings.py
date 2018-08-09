import os
import shutil

texta_docker_dir = os.path.realpath(os.path.dirname(__file__))

try:
    os.remove(os.path.join(texta_docker_dir, 'settings.py'))
except:
    pass

print('Copying settings.py file...')

shutil.copy2(os.path.join(texta_docker_dir, '../../texta/settings.py'), os.path.join(texta_docker_dir, 'settings.py'))

print('Adding custom Elasticsearch URL...')

with open(os.path.join(texta_docker_dir, 'settings.py'), 'a') as settings_file:
    settings_file.write('\n')
    settings_file.write("es_url = 'http://texta-elastic:9200'\n")

print('Done!')