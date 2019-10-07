import subprocess
import sys


class DockerBuilder:

    def __init__(self, project, version, tag_suffix="", dockerfile="./docker/Dockerfile"):
        self.project = project
        self.version = version
        self.tag_suffix = tag_suffix
        self.dockerfile = dockerfile
        self.version_tag = version+tag_suffix
        self.latest_tag = "latest"+tag_suffix
    
    def build(self):
        build_command = "docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/{0}:{1} -f {2} .".format(self.project, self.version_tag, self.dockerfile)
        print("Building, tagging and pushing Docker image for version {0}.".format(self.version_tag))
        print("Building...")
        built = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE)
        built_id = built.communicate()[0].strip().split('\n')[-2].split()[-1]
        print("Built {0}.".format(built_id))
        return built_id

    def tag_latest(self, built_id):
        print("Tagging latest...")
        tag_command = "docker tag {0} docker.texta.ee/texta/{1}:{2}".format(built_id, self.project, self.latest_tag)
        tagged = subprocess.Popen(tag_command, shell=True)
        print("Tagged")
        return True

    def test(self):
        # TODO: confirm if tests success
        print("Running tests...")
        test_command = "docker run docker.texta.ee/texta/{0}:{1} python manage.py test".format(self.project, self.latest_tag)
        tested = subprocess.Popen(test_command, shell=True, stdout=subprocess.PIPE)
        print("Tests output:",tested.communicate()[0])

    def push(self):
        for tag in [self.latest_tag, self.version_tag]:
            print("Pushing {0}...".format(tag))
            push_command = "docker push docker.texta.ee/texta/{0}:{1}".format(self.project, tag)
            pushed = subprocess.Popen(push_command, shell=True)
            print("Pushed {0}.".format(tag))
        return True

def main():
    try:
        # declare project name
        project = "texta-rest"
        # load version from file system
        with open("VERSION") as fh:
            version = fh.read()
        # build CPU version
        db = DockerBuilder(project, version)
        built_id = db.build()
        # tag latest
        db.tag_latest(built_id)
        # test
        #db.test()
        # push
        db.push()
    except Exception as e:
        print("Build failed:", e)
        return

if __name__ == "__main__": 
    main()
