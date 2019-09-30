import requests
import subprocess


def main():
    try:
        with open("VERSION") as fh:
            version = fh.read()
            build_command = f"docker build -t docker.texta.ee/texta/texta-rest:{version}"
            print(f"Building, tagging and pushing Docker image for version {version}.")
            print("Building...")
            built = subprocess.Popen(build_command, shell=True, stdout=subprocess.PIPE)
            built_id = built.communicate()[0].strip().split('\n')[-2].split()[-1]
            print("Tagging latest...")
            tag_command = "docker tag {version} docker.texta.ee/texta/texta-rest:latest"
            tagged = subprocess.Popen(tag_command, shell=True)
            for tag in [version, "latest"]:
                print(f"Pushing {tag}...")
                push_command = f"docker push docker.texta.ee/texta/texta-rest:{tag}"
                pushed = subprocess.Popen(push_command, shell=True)
                print(f"Pushed {tag}.")
    except as e:
        print("Build failed:", e)
        return

if __name__ == "__main__": 
    main()
