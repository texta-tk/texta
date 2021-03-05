#!/bin/bash

# retrieve version from file
version_file="./VERSION"
version=$(cat "$version_file")

# build latest image
docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/texta-rest:latest -f ./docker/Dockerfile .

docker tag docker.texta.ee/texta/texta-rest:latest docker.texta.ee/texta/texta-rest:$version
docker push docker.texta.ee/texta/texta-rest:$version
docker push docker.texta.ee/texta/texta-rest:latest

# build latest GPU image
#docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/texta-rest:latest-gpu -f ./docker/gpu.Dockerfile .

#docker tag docker.texta.ee/texta/texta-rest:latest-gpu docker.texta.ee/texta/texta-rest:$version-gpu
#docker push docker.texta.ee/texta/texta-rest:$version-gpu
#docker push docker.texta.ee/texta/texta-rest:latest-gpu
