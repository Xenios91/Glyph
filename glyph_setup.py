import os
import subprocess
from os.path import expanduser


def download() -> str:
    os.system("wget https://search.maven.org/remotecontent?filepath=com/google/code/gson/gson/2.8.6/gson-2.8.6.jar")
    get_pwd = subprocess.Popen(["pwd"], stdout=subprocess.PIPE)
    download_location = get_pwd.communicate()[0].decode("utf-8").strip()
    return download_location

def make_dir() -> str:
    home = expanduser("~")
    directory = "plugins"
    parent_dir = "{0}/.ghidra/.ghidra_9.1.2_PUBLIC".format(home)
    path = os.path.join(parent_dir, directory)
    try:
        os.mkdir(path)
    except Exception as e:
        print(e)
    print("Directory created at {0}".format(path))
    return path

def install(download_location: str):
    path = make_dir()
    os.system("mv {0} {1}".format(download_location, path))

def main():
    print("Downloading and installing ghidra script dependencies...")
    download_location = download()
    install(download_location)
    print("Installation complete!")


main()
