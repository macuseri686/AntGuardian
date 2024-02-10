import urwid
import time
import datetime
import socket
import requests
from requests.auth import HTTPDigestAuth
import json
import nmap
import math

# Configuration
USER = 'root'
PASS = 'root'
SECONDS_4_CHECKS = 95
SECONDS_TO_INTERNET = 60

log_messages = []

class Miner(object):
    def __init__(self, ip):
        self.__ip = ip
        self.__acceptedShares = 0
        self.__updateCount = 0
        self.__lastUpdated = datetime.datetime.now()
        self.__lastRebooted = datetime.datetime.now()
        self.__hashrate = 0
        self.__uptime = datetime.timedelta(seconds=1)
        self.__minerType = ''
        self.__alive = False
        self.__active = False
        self.initialize_miner()

    def initialize_miner(self):
        try:
            with requests.get(f'http://{self.__ip}/cgi-bin/get_system_info.cgi', auth=HTTPDigestAuth(USER, PASS)) as r:
                cont = str(r.content)
                cont= cont[cont.find('Antminer'):]
                cont= cont[:cont.find('"')]
                self.__minerType = cont
                self.__alive = True
                if not cont:
                    self.__alive=False
        except Exception as e:
            self.__alive = False
        return self.__alive

    def update(self):
        self.__updateCount += 1
        self.__lastUpdated = datetime.datetime.now()
        try:
            with requests.get(f'http://{self.__ip}/cgi-bin/pools.cgi', auth=HTTPDigestAuth(USER, PASS)) as r:
                log_message(f"Checking {self.__ip}...")
                cont = json.loads(r.text)
                if self.__acceptedShares != 0 and int(cont['POOLS'][0]['accepted']) == self.__acceptedShares and self.__active == True:
                    self.__active = False
                    self.reboot()
                else:
                    self.__acceptedShares = int(cont['POOLS'][0]['accepted'])
                    self.__active = True
            
            with requests.get(f'http://{self.__ip}/cgi-bin/stats.cgi', auth=HTTPDigestAuth(USER, PASS)) as r:
                cont = json.loads(r.text)
                self.__hashrate = int(cont['STATS'][0]['rate_5s'])
                
                if int(cont['STATS'][0]['elapsed']) > 0:
                    seconds = int(cont['STATS'][0]['elapsed'])
                else:
                    seconds = 1
                self.__uptime = datetime.timedelta(seconds=seconds)
                self.__lastRebooted = datetime.datetime.now() - datetime.timedelta(seconds=self.__uptime)

            return out
        except Exception as e:
            return 0

    def reboot(self):
        try:
            log_message(f"Rebooting {self.__ip}...")
            requests.get(f'http://{self.__ip}//cgi-bin/reboot.cgi', auth=HTTPDigestAuth(USER, PASS))
            self.__lastRebooted = datetime.datetime.now()
            self.__alive = False
        except Exception as e:
            self.__alive = False

    def get_info(self):
        last_reboot = self.__lastRebooted.strftime('%-m-%-d %I:%M %p')
        # uptime in days, hours and minutes
        uptime = f"{self.__uptime.days}D {self.__uptime.seconds//3600}H {(self.__uptime.seconds//60)%60}M"
        active_status = "Yes" if self.__active else "No"
        return f"{self.__ip}, {self.__minerType}, {self.__acceptedShares}, {uptime}, {active_status}"


def internet(host="8.8.8.8", port=53, timeout=3):
    try:
        socket.setdefaulttimeout(timeout)
        socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect((host, port))
        return True
    except Exception as ex:
        return False

def discover_miners():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM) #Get list of IPs from local network
    s.connect(('192.168.1.1', 80))
    myIP = s.getsockname()[0]
    s.close()
    ipRange = myIP[:-3] + '0/24'
    nm = nmap.PortScanner()
    nm.scan(hosts=ipRange, arguments='-sn')
    ipList = nm.all_hosts()
    return ipList

def update_display(loop, data):
    header, miner_list, table, log_listbox = data
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
    header.set_text(('header', f"AntGuardian - {current_time}"))
    
    for miner in miner_list:
        # only update every SECONDS_4_CHECKS seconds by checking the last time it was updated
        if (datetime.datetime.now() - miner._Miner__lastUpdated).seconds > SECONDS_4_CHECKS or miner._Miner__updateCount == 0:
            miner.update()
        
    table_contents = [
        (urwid.AttrMap(urwid.Padding(urwid.Text('IP Address'), left=1, right=1), 'table_header'), table.options()),
        (urwid.AttrMap(urwid.Padding(urwid.Text('Miner Type'), left=1, right=1), 'table_header'), table.options()),
        (urwid.AttrMap(urwid.Padding(urwid.Text('Hashrate'), left=1, right=1), 'table_header'), table.options()),
        (urwid.AttrMap(urwid.Padding(urwid.Text('Shares'), left=1, right=1), 'table_header'), table.options()),
        (urwid.AttrMap(urwid.Padding(urwid.Text('Uptime'), left=1, right=1), 'table_header'), table.options()),
        (urwid.AttrMap(urwid.Padding(urwid.Text('Active'), left=1, right=1), 'table_header'), table.options())
    ]
    for miner in miner_list:
        ip, miner_type, shares, uptime, active = miner.get_info().split(', ')
        table_contents.append((urwid.Text(ip), table.options()))
        table_contents.append((urwid.Text(miner_type), table.options()))
        table_contents.append((urwid.Text(str(miner._Miner__hashrate)+ " GH/s"), table.options()))
        table_contents.append((urwid.Text(shares), table.options()))

        # if uptime is 30 mins or less, highlight it in red
        if miner._Miner__uptime.seconds < 1800:
            table_contents.append((urwid.AttrMap(urwid.Text(uptime), 'highlight_red'), table.options()))
        else:
            table_contents.append((urwid.Text(uptime), table.options()))

        if active == "Yes":
            table_contents.append((urwid.AttrMap(urwid.Text(" "+active), 'highlight_green'), table.options()))
        else:
            table_contents.append((urwid.AttrMap(urwid.Text(" "+active), 'highlight_red'), table.options()))


    table.contents = table_contents
    
    # if the size of the terminal has changed, update the table size
    current_terminal_width = urwid.raw_display.Screen().get_cols_rows()[0]-6
    table.cell_width = math.floor(current_terminal_width/6)

    # Update log messages display
    log_listbox.body = urwid.SimpleFocusListWalker([urwid.Text(message) for message in log_messages])

    log_listbox.set_focus(len(log_messages)-1)
    
    loop.set_alarm_in(1, update_display, data)  # Update every second for the clock

def log_message(message):
    global log_messages
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
    log_messages.append(f"{current_time} - {message}")

def main():
    global log_messages
    while not internet():
        log_message("Waiting for internet connection...")
        time.sleep(5)

    miner_ips = discover_miners()
    miner_list = [Miner(ip) for ip in miner_ips if Miner(ip).initialize_miner()]

    header_text = urwid.Text(('header', "AntGuardian"), align='center')
    current_terminal_width = urwid.raw_display.Screen().get_cols_rows()[0]-6
    table = urwid.GridFlow([], cell_width=math.floor(current_terminal_width/6), h_sep=1, v_sep=0, align='left')

    header = urwid.AttrMap(header_text, 'header')
    body = urwid.LineBox(table, title="Miners")

    log_listbox = urwid.ListBox(urwid.SimpleFocusListWalker([urwid.Text(message) for message in log_messages]))
    log_box = urwid.LineBox(log_listbox, title="Log Messages")

    pile_contents = [
        body,
        ('fixed', 7, log_box)
    ]

    pile = urwid.Pile(pile_contents)

    frame = urwid.Frame(pile, header=header)


    palette = [
        ('header', 'white,bold', 'dark red'),
        ('table_header', 'black,bold', 'white'),
        ('highlight_green', 'white', 'dark green'),
        ('highlight_red', 'white', 'dark red')
    ]

    loop = urwid.MainLoop(frame, palette)
    loop.set_alarm_in(1, update_display, (header_text, miner_list, table, log_listbox))
    loop.run()

if __name__ == "__main__":
    main()
