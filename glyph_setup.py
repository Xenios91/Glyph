import os
import argparse
import subprocess
from os.path import expanduser


main_logo = """
   _____ _             _       _____           _        _ _
  / ____| |           | |     |_   _|         | |      | | |
 | |  __| |_   _ _ __ | |__     | |  _ __  ___| |_ __ _| | | ___ _ __
 | | |_ | | | | | '_ \| '_ \    | | | '_ \/ __| __/ _` | | |/ _ \ '__|
 | |__| | | |_| | |_) | | | |  _| |_| | | \__ \ || (_| | | |  __/ |
  \_____|_|\__, | .__/|_| |_| |_____|_| |_|___/\__\__,_|_|_|\___|_|
            __/ | |
           |___/|_|

More info: https://github.com/Xenios91/Glyph
"""

def download() -> str:
    os.system("wget https://search.maven.org/remotecontent?filepath=com/google/code/gson/gson/2.8.6/gson-2.8.6.jar")
    get_pwd = subprocess.Popen(["pwd"], stdout=subprocess.PIPE)
    download_location = get_pwd.communicate()[0].decode("utf-8").strip()
    return download_location

def make_dir(ghidra_version: str) -> str:
    home = expanduser("~")
    directory = "plugins"
    parent_dir = "{0}/.ghidra/.ghidra_{1}_PUBLIC".format(home, ghidra_version)
    path = os.path.join(parent_dir, directory)
    try:
        os.mkdir(path)
    except Exception as e:
        print(e)
    print("Directory created at {0}".format(path))
    return path

def install_json_lib(download_location: str, ghidra_version: str):
    path = make_dir(ghidra_version)
    os.system("mv {0} {1}".format(download_location, path))

def get_args() -> list:
    parser = argparse.ArgumentParser()
    parser.add_argument("--gv", type=str, help="The version of ghidra you are using. Example: --gv 9.2 indicates [ghidra_9.2_PUBLIC]", required=True)
    args = parser.parse_args()
    return args

def main():
    print(main_logo)
    args = get_args()
    print("Downloading and installing ghidra script dependencies...")
    download_location = download()
    install_json_lib(download_location, args.gv)
    print("Installation of Ghidra script dependencies complete!")


main()
