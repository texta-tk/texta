import subprocess
import os
import codecs

class ScriptRunner(object):

    def __init__(self, script_project, script_manager_dir):
        self._script_project = script_project
        self._script_manager_dir = script_manager_dir

    def run(self):
        arguments = self._script_project.arguments.split('\n')

        os.chdir(os.path.join(self._script_manager_dir, "%s_%s" % (str(self._script_project.id), self._canonize_project_name(self._script_project.name))))

        with codecs.open('_script_manager.stdout', 'w') as stdout_file:
            process = subprocess.Popen(["python", self._script_project.entrance_point] + arguments, stdout=stdout_file)
            pid = process.pid

    def _canonize_project_name(self, name):
        return name.lower().replace(' ', '_')
