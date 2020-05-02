#!/bin/bash
set -e

LAYER_NAME=awesome-aws-sdk

../../layer-tool.py --list
../../layer-tool.py --build "$LAYER_NAME"
du -h "$LAYER_NAME.zip"
../test-zip-file.py "$LAYER_NAME.zip" \
                    nodejs/package-lock.json \
                    nodejs/layer.yaml \
                    nodejs/npm-list.txt \
                    nodejs/node_modules/aws-sdk/index.js
