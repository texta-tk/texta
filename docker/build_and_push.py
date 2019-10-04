import subprocess
import sys


def build(project, version, tag_suffix="", dockerfile="./docker/Dockerfile"):
    # build image
    build_command = "docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/{0}:{1}{2} -f {3} .".format(project, version, tag_suffix, dockerfile)
    print("Building, tagging and pushing Docker image for version {0}{1}.".format(version, tag_suffix))
    print("Building...")
    built = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE)
    built_id = built.communicate()[0].strip().split('\n')[-2].split()[-1]
    # tag latest
    print("Tagging latest...")
    tag_command = "docker tag {0} docker.texta.ee/texta/{1}:latest{2}".format(built_id, project, tag_suffix)
    tagged = subprocess.Popen(tag_command, shell=True)
    # push
    for tag in [version, "latest"]:
        print("Pushing {0}{1}...".format(tag, tag_suffix))
        push_command = "docker push docker.texta.ee/texta/{0}:{1}{2}".format(project, tag, tag_suffix)
        pushed = subprocess.Popen(push_command, shell=True)
        print("Pushed {0}{1}.".format(tag, tag_suffix))


def main():
    try:
        # declare project name
        project = "texta-rest"
        # load version from file system
        with open("VERSION") as fh:
            version = fh.read()
        # build CPU version
        build(project, version)
        # build GPU version
        #build(project, version, tag_suffix="-gpu", dockerfile="./docker/gpu.Dockerfile")
    except Exception as e:
        print("Build failed:", e)
        return

if __name__ == "__main__": 
    main()
