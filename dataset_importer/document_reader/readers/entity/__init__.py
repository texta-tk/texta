import os, sys
file_dir = os.path.dirname(__file__)
sys.path.append(file_dir)

try:
    import doc_reader as doc
except:
    print('failed to import doc_reader as doc')

try:
    import docx_reader as docx
except:
    print('failed to import docx_reader as docx')

try:
    import html_reader as html
except:
    print('failed to import html_reader as html')

try:
    import pdf_reader as pdf
except:
    print('failed to import pdf_reader as pdf')

try:
    import rtf_reader as rtf
except:
    print('failed to import rtf_reader as rtf')

try:
    import txt_reader as txt
except:
    print('failed to import text_reader as txt')
