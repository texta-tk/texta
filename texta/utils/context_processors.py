# -*- coding: utf8 -*-
import os
from pathlib import Path

def get_version(request):
    try:
        current_path = Path(os.path.dirname(os.path.realpath(__file__)))
        version_file_path = os.path.join(str(current_path.parent.parent),"VERSION")
        with open(version_file_path, "r")as fh:
            version = fh.read()
    except:
        version = "UNKNOWN"
    return {"texta_version": version}
