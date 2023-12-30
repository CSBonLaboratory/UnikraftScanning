#!/bin/bash
cd ./apps/app-helloworld
wget https://scan.coverity.com/download/linux64 --post-data "token=${COVERITY_UPLOAD_TOKEN}&project=${COVERITY_PROJECT_NAME}" -O coverity_tool.tgz
tar zxvf coverity_tool.tgz
export UK_WORKDIR=/home/runner/work/UnikraftScanning/UnikraftScanning
export UK_ROOT=/home/runner/work/UnikraftScanning/UnikraftScanning/unikraft
export UK_LIBS=/home/runner/work/UnikraftScanning/UnikraftScanning/libs
ls -lrt
./cov-analysis-linux64-*/bin/cov-build --dir cov-int make
tar czvf analysis_input.tgz cov-int
curl --form token="$COVERITY_UPLOAD_TOKEN" --form email=csbon420@protonmail.com --form "file=@./analysis_input.tgz" --form version=1 --form description="Submited via Github action" https://scan.coverity.com/builds?project=Unikraft-Scanning
