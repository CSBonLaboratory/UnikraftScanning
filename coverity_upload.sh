#!/bin/bash
cd ./apps/app-helloworld
wget https://scan.coverity.com/download/linux64 --post-data "token=_5PXI3ZAJ4wN2hGlCdZhJA&project=Unikraft-Scanning" -O coverity_tool.tgz
tar zxvf coverity_tool.tgz
export UK_WORKDIR=/home/runner/work/UnikraftScanning/UnikraftScanning
export UK_ROOT=/home/runner/work/UnikraftScanning/UnikraftScanning/unikraft
export UK_LIBS=/home/runner/work/UnikraftScanning/UnikraftScanning/libs
./cov-analysis-linux64-2022.6.0/bin/cov-build --dir cov-int make
tar czvf analysis_input.tgz cov-int
curl --form token=_5PXI3ZAJ4wN2hGlCdZhJA --form email=csbon420@protonmail.com --form "file=@./analysis_input.tgz" --form version=1 --form description="Using github actions first try" https://scan.coverity.com/builds?project=Unikraft-Scanning
