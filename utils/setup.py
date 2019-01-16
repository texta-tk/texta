import os

SETUP_FILES_DIR = os.path.join(os.path.realpath(os.path.dirname(__file__)),'setup_files')

def write_navigation_file(link_prefix, static_url, static_root):
    
    variables_template = """var LINK_PREFIX = '{link_prefix}';\nvar STATIC_URL = '{static_url}';\n\n"""
    
    variables = {'link_prefix':link_prefix, 'static_url':static_url}
    
    with open(os.path.join(SETUP_FILES_DIR,'raw_navigation.js'),'r') as fin,\
         open(os.path.join(static_root,'navigation.js'),'w') as fout:

         raw_navigation_content = fin.read()
         
         fout.write(variables_template.format(**variables))
         
         fout.write(raw_navigation_content)
         
def ensure_dir_existence(path):
    if not os.path.exists(path):
        os.makedirs(path)
