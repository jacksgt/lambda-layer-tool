#!/usr/bin/env python3

import argparse
import sys
import zipfile

def main():
    parser = argparse.ArgumentParser(prog=__name__,
                                     description='Tests if a file exists in ZIP archive')
    parser.add_argument("archive", help="The ZIP archive to inspect")
    parser.add_argument("filenames", help="Names of files that should be present in the archive", nargs="+")

    args = parser.parse_args()

    sys.exit(test_archive(args.archive, args.filenames))

def test_archive(filename, testfiles):
    try:
        archive = zipfile.ZipFile(filename)
    except Exception as e:
        print("ERROR: Failed to open {}: {}".format(filename, e))
        return -1

    files = archive.namelist()
    archive.close()

    errors = 0
    for t in testfiles:
        if t not in files:
            print("ERROR: Could not find file {} in archive {}".format(t, filename))
            errors += 1

    if errors != 0:
        print("Failed to find {} file(s) in archive {}".format(errors, filename))
    else:
        print("OK: Successfully found {} file(s) in archive {}".format(len(testfiles), filename))

    return errors

if __name__ == "__main__":
    main()
