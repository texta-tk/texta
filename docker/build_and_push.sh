#!/bin/bash

# retrieve version from file
version_file="./VERSION"
version=$(cat "$version_file")

# build latest image
docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/texta-rest:latest -f ./docker/Dockerfile .

# build latest GPU image
docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/texta-rest:latest-gpu -f ./docker/gpu.Dockerfile .

# tag version
docker tag docker.texta.ee/texta/texta-rest:latest docker.texta.ee/texta/texta-rest:$version
docker tag docker.texta.ee/texta/texta-rest:latest-gpu docker.texta.ee/texta/texta-rest:$version-gpu

# push version tag
docker push docker.texta.ee/texta/texta-rest:$version
docker push docker.texta.ee/texta/texta-rest:$version-gpu

# push latest tag
docker push docker.texta.ee/texta/texta-rest:latest
docker push docker.texta.ee/texta/texta-rest:latest-gpu
