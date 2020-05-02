#!/bin/bash
set -e

LAYER_NAME=awesome-numpy

../../layer-tool.py --list
../../layer-tool.py --build "$LAYER_NAME"
du -h "$LAYER_NAME.zip"
../test-zip-file.py "$LAYER_NAME.zip" \
                    python/layer.yaml \
                    python/hello-world.txt \
                    python/lib/python3.7/site-packages/numpy/version.py
