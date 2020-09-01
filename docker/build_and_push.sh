#!/bin/bash

# retrieve version from file
version_file="./VERSION"
version=$(cat "$version_file")

# build latest image
docker build --compress --force-rm --no-cache -t docker.texta.ee/texta/texta-rest:latest -f ./docker/Dockerfile .

# tag version
docker tag docker.texta.ee/texta/texta-rest:latest docker.texta.ee/texta/texta-rest:$version

# push version tag
docker push docker.texta.ee/texta/texta-rest:$version

# push latest tag
docker push docker.texta.ee/texta/texta-rest:latest
