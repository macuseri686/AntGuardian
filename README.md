# AntGuardian (updated)

*updated to support latest antminer protocol, and with more fuctional UI

AntMiner monitor and auto-restart tool

Compatible with all AntMiners from Bitmain. Works on Linux, Windows and Mac OS

Scans the local network for miners. Once connected, restarts any miner when accepted shares do not increase in SECONDS_4_CHECKS seconds, given that there is an active internet connection (checks with google.com).

This software and all its dependencies are free and open source. Free as in free speach not as in free beer, meaning it respects your freedom! Please star on GitHub and share with your miner friends!

### Screenshot

![Screenshot from 2024-02-09 18-42-00](https://github.com/macuseri686/AntGuardian/assets/1278401/bc21c9bc-f016-47c0-9686-d800d81adb6b)


### Prerequisites

* NMap

Download and install NMap. Link:
https://nmap.org/download.html

* Python

Most Mac and Linux distributions come with Python pre-installed. For windows and other systems, you may need to download and install Python first. Link:
https://www.python.org/downloads/

* PIP - Python Package Installer
https://pip.pypa.io/en/stable/installing/

### Installation

Download the AntGuardian repository and unzip it. Link:
https://github.com/macuseri686/AntGuardian

* Install Python requirements

Using the command prompt, navigate to directory Downloads/AntGuardian and run the command:


INSTALL COMMAND:
```sh
pip install -r requirements.txt
```
If you have problems running PIP directly, try with this command:
```sh
python3 -m pip install -r requirements.txt 
```

### Setup

If you have changed the password of your miners from the default "root", you must change the PASS varieble in the script file "AntGuardian.py", for the actual password. Otherwise, you are ready to run the script.

```sh
USER = 'root'
PASS = 'root' # Replace with your miner's password
SECONDS_4_CHECKS = 95 # you need at least 6 seconds per miner, increase this number if monitoring 16 miners or more
```

### Running
Using the command prompt, while in the directory Downloads/AntGuardian, run the program by entering the command:

RUN COMMAND: 
```sh 
python AntGuardian.py
```

## Options
You may also change the time intervals (seconds): <br />

* SECONDS_4_CHECKS: 
Time to wait between each check for accepted shares. <br />

## Troubleshooting:
-If you have any problems installing requirements, try a different version of Python. You might have multiple versions installed in your computer. If trouble persists. Uninstall all versions of Python and start from scratch 

## Authors

**Caleb Banzhaf** - *Update work to support new antminers and reworked UI* - [macuseri686](https://github.com/macuseri686)

**Ricardo Solano** - *Initial work* - [RSolano](https://github.com/rsolano60)

See also the list of [contributors](https://github.com/rsolano60/AntGuardian/graphs/contributors) who participated in this project.

## License

This project is licensed under the GNU GPL V3 License - see the [LICENSE](LICENSE) file for details
