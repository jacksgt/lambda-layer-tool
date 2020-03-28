# Lambda Layer Tool

A tool to programmatically build and publish Layers for AWS Lambda.

Instead of manually copy & pasting build instructions for a Lambda Layer into your shell or trying to script your way around, use this tool to automate the process.
Given a simple YAML file, it will install the specified dependencies in a clean environment, strip any binaries inside, apply exclusion patterns and bundle everything up into an archive.
Then, you can use the tool to publish the new layer (version) on AWS.

Here is a simple example:
```yaml
---
version: '0.3'
layers:
  awesome-numpy:
    description: 'Minimal numpy 1.18'
    runtimes: 'python3.6'
    requirements:
      - 'numpy==1.18.2'
    excludes:
      - '*/numpy/tests/*'
      - '*.dist-info/*'
      - '*.egg-info/*'
      - '*/__pycache__/*'
      - '*.pyc'
```

Then just run:
```
$ ./layer-tool.py --build awesome-numpy
[...]

$ du -h awesome-numpy.zip
13M

$ ./layer-tool.py --publish awesome-numpy
{
    "Content": {
        "Location": "https://example.com/aws",
        "CodeSha256": "xxQC6FDxg63M5m2UL2cXmChD+dFX7fp61LRrrqmVjGY=",
        "CodeSize": 13590501
    },
    "LayerArn": "arn:aws:lambda:$AWS_REGION:$AWS_ID:layer:awesome-numpy",
    "LayerVersionArn": "arn:aws:lambda:$AWS_REGION:$AWS_ID:layer:awesome-numpy:1",
    "Description": "Minimal numpy 1.18 for python3.7",
    "CreatedDate": "2020-03-28T07:40:49.714+0000",
    "Version": 1,
    "CompatibleRuntimes": [
        "python3.7"
    ]
}
```

## Lambda Environment

To match the environment of AWS Lambda functions as closely as possible (especially when you use this tool on non-Linux systems), the tool should be run inside a Docker container.
The [lambci/lambda Docker image]() closely resembles the real Lambda environment and is well-suited for this task.
Example:

```
docker run --rm -v "$PWD:/var/task" lambci/lambda:build-python3.7 ./layer-tool.py --build awesome-numpy
```

## Publishing

Publishing assumes you have previously configured the aws-cli to connect to your AWS account.

**Note**: Publishing *always* creates a new version of your layer. For more information see https://docs.aws.amazon.com/lambda/latest/dg/configuration-layers.html .

## Dependencies

In addition to the Python dependencies (`requirements.txt`), this tool currently needs the following command line tools:

* aws-cli (aws)
* find
* zip

## License

This software is license under the [MIT License](https://spdx.org/licenses/MIT.html).
See `LICENSE`.
