import requests
import subprocess


def main():
    try:
        with open("VERSION") as fh:
            version = fh.read()
            build_command = "docker build -t docker.texta.ee/texta/texta-rest:{}".format(version)
            print("Building, tagging and pushing Docker image for version {}.".format(version))
            print("Building...")
            built = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE)
            built_id = built.communicate()[0].strip().split('\n')[-2].split()[-1]
            print("Tagging latest...")
            tag_command = "docker tag {} docker.texta.ee/texta/texta-rest:latest".format(built_id)
            tagged = subprocess.Popen(tag_command, shell=True)
            for tag in [version, "latest"]:
                print("Pushing {}...".format(tag))
                push_command = "docker push docker.texta.ee/texta/texta-rest:{}".format(tag)
                pushed = subprocess.Popen(push_command, shell=True)
                print("Pushed {}.".format(tag))
    except as e:
        print("Build failed:", e)
        return

if __name__ == "__main__": 
    main()
