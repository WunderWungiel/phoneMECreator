#!/usr/bin/env python3

import shutil
import sys
import os
from zipfile import ZipFile
import subprocess
import base64
import json

import requests

blue='\033[96m'
red='\033[31m'
reset='\033[0m'
green='\033[32m'
blink='\033[5m'
yellow='\033[33m'
cyan='\033[1;36m'

config = {}
commands = ("dpkg-deb", "magick")

def generate_sums():

    subprocess.run("find -type f | grep -v \"./DEBIAN\" > ../md5", shell=True)
    subprocess.run('''while read line; do if [ -f "$line" ]; then line=`echo "$line" | cut -c 3-`; md5sum "$line" >> DEBIAN/md5sums; echo S 15 com.nokia.maemo H 40 `sha1sum "$line" | cut -c -40` R `expr length "$line"` $line >> DEBIAN/digsigsums; fi; done < "../md5"''', shell=True)
    os.remove("../md5")


def get_size():
    result = subprocess.run("du -c opt usr | grep total | awk '{print $1}'", shell=True, env={"LANG": "C"}, text=True, capture_output=True)
    return result.stdout.strip()

def check_commands(commands):
    for command in commands:
        if not shutil.which(command):
            print(f"{red}{command} not available!{reset}")
            sys.exit(0)

def package():

    
    for directory in ("tmp", "jar_tmp", "app.jar"):
    
        if os.path.isfile(directory):
            os.remove(directory)
        elif os.path.isdir(directory):
            shutil.rmtree(directory)

    os.mkdir("tmp")
    os.chdir("tmp")
    os.mkdir("DEBIAN")
    os.makedirs("usr/share")
    os.makedirs("opt/phoneme")
    os.makedirs("usr/share/icons/hicolor/80x80/apps")
    os.makedirs("usr/share/icons/hicolor/scalable/apps")
    os.makedirs("usr/share/applications/hildon")
    os.mkdir("jar_tmp")

    print(f"{green}Environment prepared successfully.{reset}")

    if config.get("path"):
        shutil.copyfile(os.path.join("..", config["path"]), "app.jar")
    else:
        r = requests.get(config["link"])
        with open("app.jar", "wb") as f:
            f.write(r.content)

    print(f"{green}JAR file saved successfully.{reset}")

    with ZipFile("app.jar", "r") as f:
        f.extractall("jar_tmp")

    print(f"{green}JAR file extracted successfully.{reset}")

    version = None
    with open("jar_tmp/META-INF/MANIFEST.MF", "r") as f:
        for line in f.readlines():
            if "MIDlet-Version" in line:
                version = line.split(":")[1].strip()

    if not version:
        print(f"{red}Version string not found!{reset}")
        sys.exit(0)

    size = get_size()

    subprocess.run(["magick", "jar_tmp/icon.png", "-trim", "icon80.png"])
    subprocess.run(["magick", "icon80.png", "-resize",  "64x64^", "-gravity", "center", "-extent", "64x64", "-background", "transparent", "icon64.png"])

    print(f"{green}Icon converted successfully.{reset}")

    shutil.copyfile("app.jar", f"opt/phoneme/{config['package_name']}.jar")
    shutil.rmtree("jar_tmp")
    os.remove("app.jar")

    harmattan_desktop = f"""[Desktop Entry]
Encoding=UTF-8
Version=1.0
Type=Application
Name={config['pretty_name']}
Exec=/opt/phoneme/bin/runmidlet /opt/phoneme/{config['package_name']}.jar
Icon=/usr/share/icons/hicolor/80x80/apps/{config['package_name']}80.png
X-HildonDesk-ShowInToolbar=true
X-Osso-Type=application/x-executable
"""
    
    fremantle_desktop = f"""[Desktop Entry]
Encoding=UTF-8
Version=1.0
Type=Application
Name={config['pretty_name']}
Exec=/opt/phoneme/bin/runmidlet /opt/phoneme/{config['package_name']}.jar
Icon={config['package_name']}64
X-HildonDesk-ShowInToolbar=true
X-Osso-Type=application/x-executable
"""
    
    with open(f"usr/share/applications/{config['package_name']}.desktop", "w") as f:
        f.write(harmattan_desktop)
    with open(f"usr/share/applications/hildon/{config['package_name']}.desktop", "w") as f:
        f.write(fremantle_desktop)
    
    print(f"{green}Desktop files generated.{reset}")

    shutil.copyfile("icon80.png", f"usr/share/icons/hicolor/80x80/apps/{config['package_name']}80.png")
    shutil.copyfile("icon64.png", f"usr/share/icons/hicolor/scalable/apps/{config['package_name']}64.png")

    with open("icon80.png", "rb") as f:
        icon_base64 = base64.b64encode(f.read()).decode("utf-8")
        formatted_icon_base64 = " " + "\n ".join(icon_base64[i:i+76] for i in range(0, len(icon_base64), 76))

    os.remove("icon64.png")
    os.remove("icon80.png")

    control = f"""Package: {config['package_name']}
Version: {version}
Architecture: {config['arch']}
Maintainer: {config['maintainer']}
Installed-Size: {size}
Depends: cvm, unzip
Section: ${config['section']}
Priority: optional
Homepage: {config['homepage']}
Description: {config['description']}
Maemo-Display-Name: {config['pretty_name']}
Maemo-Flags: visible
Maemo-Icon-26:
{formatted_icon_base64}
"""
    
    with open("DEBIAN/control", "w") as f:
        f.write(control)

    print(f"{green}Control file generated successfully.{reset}")
    
    generate_sums()

    print(f"{green}Checksums generated successfully.{reset}")
    os.chdir("..")

    filename = f"{config['package_name']}_{version}_{config['arch']}.deb"
    result = subprocess.run(["dpkg-deb", "-b", "--root-owner-group", "-Zgzip", "tmp/", filename], stdout=subprocess.DEVNULL)
    if result.returncode != 0:
        print(f"{red}Error while packaging.{reset}")
        sys.exit(0)

    shutil.rmtree("tmp")

    print(f"\n{green}Package {config['package_name']} generated successfully. File: {filename}.{reset}")

def main():

    global config

    if not len(sys.argv) > 1:
        print(f"Usage: {sys.argv[0]} <config.json>")
        sys.exit(0)

    config_path = sys.argv[1]

    if not os.path.exists(sys.argv[1]):
        print(f"{red}Config file not found!{reset}")
        sys.exit(0)

    config = json.loads(open(config_path, "r").read())
    if config.get("path"):
        if not os.path.isfile(config["path"]):
            print(f"{red}Specified JAR file not found!{reset}")
            sys.exit(0)

    check_commands(commands)
    package()

if __name__ == "__main__":
    main()
