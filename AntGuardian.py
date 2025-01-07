import urwid
import time
import datetime
import socket
import requests
from requests.auth import HTTPDigestAuth
import json
import nmap
import math
from functools import partial

# Configuration
USER = 'root'
PASS = 'root'
SECONDS_4_CHECKS = 95
SECONDS_TO_INTERNET = 60

log_messages = []
log_focus = 0

class Miner(object):
    def __init__(self, ip):
        self.__ip = ip
        self.__acceptedShares = 0
        self.__updateCount = 0
        self.__lastUpdated = datetime.datetime.now()
        self.__lastRebooted = datetime.datetime.now()
        self.__hashrate = 0
        self.__initialHashrate = None  # Added to store initial hashrate
        self.__uptime = datetime.timedelta(seconds=1)
        self.__minerType = ''
        self.__alive = False
        self.__active = False
        self.__hashrate_history = [(datetime.datetime.now(), 0)]  # Initialize with a zero datapoint
        self.__max_history_points = 60  # Store last 60 points
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
                if self.__acceptedShares != 0 and int(cont['POOLS'][0]['accepted']) == self.__acceptedShares and self.__active == True and cont['POOLS'][0]["status"] != "Dead":
                    self.__active = False
                    self.reboot()
                else:
                    self.__acceptedShares = int(cont['POOLS'][0]['accepted'])
                    self.__active = True
            
            with requests.get(f'http://{self.__ip}/cgi-bin/stats.cgi', auth=HTTPDigestAuth(USER, PASS)) as r:
                cont = json.loads(r.text)
                current_hashrate = int(cont['STATS'][0]['rate_5s'])
                self.__hashrate = current_hashrate
                
                # Add hashrate to history
                self.__hashrate_history.append((datetime.datetime.now(), current_hashrate))
                # Keep only the last max_history_points
                if len(self.__hashrate_history) > self.__max_history_points:
                    self.__hashrate_history = self.__hashrate_history[-self.__max_history_points:]

                # Set initial hashrate if not set
                if self.__initialHashrate is None and current_hashrate > 0:
                    self.__initialHashrate = current_hashrate
                    log_message(f"Initial hashrate for {self.__ip}: {current_hashrate} GH/s")

                # Check for hashrate drop if we have an initial hashrate
                if self.__initialHashrate and current_hashrate > 0:
                    if current_hashrate < (self.__initialHashrate * 0.8):
                        log_message(f"Hashrate drop detected on {self.__ip}! Current: {current_hashrate} GH/s, Initial: {self.__initialHashrate} GH/s", "highlight_red")
                        self.reboot()
                
                if int(cont['STATS'][0]['elapsed']) > 0:
                    seconds = int(cont['STATS'][0]['elapsed'])
                else:
                    seconds = 1
                self.__uptime = datetime.timedelta(seconds=seconds)
                self.__lastRebooted = datetime.datetime.now() - datetime.timedelta(seconds=self.__uptime)

            return True
        except Exception as e:
            return False

    def reboot(self):
        try:
            log_message(f"Rebooting {self.__ip}...", "highlight_red")
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

class ConfirmDialog(urwid.WidgetWrap):
    def __init__(self, miner, loop, overlay):
        self.miner = miner
        self.loop = loop
        self.overlay = overlay
        
        confirm = urwid.Button("Confirm", on_press=self._confirm)
        cancel = urwid.Button("Cancel", on_press=self._cancel)
        confirm = urwid.AttrMap(confirm, 'button', focus_map='highlight_green')
        cancel = urwid.AttrMap(cancel, 'button', focus_map='highlight_red')
        
        buttons = urwid.GridFlow([confirm, cancel], 12, 3, 1, 'center')
        
        pile = urwid.Pile([
            urwid.Text(''),
            urwid.Text(f"Are you sure you want to reboot miner {miner._Miner__ip}?", align='center'),
            urwid.Text(''),
            buttons,
            urwid.Text('')
        ])
        
        fill = urwid.Filler(pile, 'middle')
        box = urwid.LineBox(
            urwid.Padding(fill, left=2, right=2),
            title="Confirm Reboot"
        )
        self._w = urwid.AttrMap(box, 'popup')
    
    def _confirm(self, button):
        log_message(f"Confirming reboot for {self.miner._Miner__ip}")
        self.miner.reboot()
        self.loop.widget = self.overlay  # Remove dialog
    
    def _cancel(self, button):
        log_message(f"Cancelled reboot for {self.miner._Miner__ip}")
        self.loop.widget = self.overlay  # Remove dialog

def handle_miner_click(loop, overlay, miner):
    try:
        log_message(f"Opening details dialog for {miner._Miner__ip}")
        
        # Create the details dialog
        dialog = MinerDetailsDialog(miner, loop, overlay)
        
        # Create a new overlay with the dialog on top
        dialog_overlay = urwid.Overlay(
            dialog,
            overlay,
            'center', ('relative', 80),
            'middle', ('relative', 80)
        )
        
        # Show the dialog
        loop.widget = dialog_overlay
        
    except Exception as e:
        import traceback
        error_msg = str(e)
        tb = traceback.format_exc()
        log_message(f"Error opening dialog: {error_msg}", "highlight_red")
        log_message(f"Traceback: {tb}", "highlight_red")

# message - string, style - string (optional)
def log_message(message, style=""):
    global log_messages
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
    
    # Create the formatted message
    formatted_message = (style, f"{current_time} - {message}") if style else (current_time + " - " + message)
    
    # Append the message
    log_messages.append(formatted_message)
    
    # Keep only the last 1000 messages to prevent memory issues
    if len(log_messages) > 1000:
        log_messages = log_messages[-1000:]

def update_display(loop, data):
    global log_focus, log_messages
    header, miner_list, table, log_listbox, loop, overlay = data
    
    current_time = datetime.datetime.now().strftime('%Y-%m-%d %I:%M:%S %p')
    header.set_text(('header', f"AntGuardian - {current_time}"))
    
    # Update miners
    for miner in miner_list:
        if (datetime.datetime.now() - miner._Miner__lastUpdated).seconds > SECONDS_4_CHECKS or miner._Miner__updateCount == 0:
            miner.update()
    
    # Update log listbox if there are messages
    if log_messages:
        log_listbox.body[:] = [urwid.Text(message) for message in log_messages]
        
        # Get current focus
        focus_pos = log_listbox.get_focus()[1]
        total_messages = len(log_messages)
        
        # Only adjust focus if we need to
        if focus_pos is None or focus_pos >= total_messages:
            if total_messages > 0:
                log_listbox.set_focus(total_messages - 1)
    
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
        
        # Create button with direct callback
        def make_callback(target_miner):
            def callback(button):
                handle_miner_click(loop, overlay, target_miner)
            return callback
        
        row_button = urwid.Button(ip, on_press=make_callback(miner))
        # Remove the < > markers from the button
        row_button._label.set_layout('left', 'clip')
        row_button = urwid.Padding(row_button, left=1, right=1)
        # Change highlight_green to button_focus for blue highlighting
        row_button = urwid.AttrMap(row_button, None, focus_map='button_focus')
        
        table_contents.append((row_button, table.options()))
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

    loop.set_alarm_in(1, update_display, data)

class MinerDetailsDialog(urwid.WidgetWrap):
    def __init__(self, miner, loop, overlay):
        self.miner = miner
        self.loop = loop
        self.overlay = overlay
        
        # Create the initial layout
        self._create_layout()
        
        # Set up periodic updates
        loop.set_alarm_in(1, self._update_dialog)
    
    def _create_layout(self):
        # Left column - Miner details
        self.details = [
            urwid.Text(f"IP Address: {self.miner._Miner__ip}"),
            urwid.Text(f"Miner Type: {self.miner._Miner__minerType}"),
            urwid.Text(f"Hashrate: {self.miner._Miner__hashrate} GH/s"),
            urwid.Text(f"Shares: {self.miner._Miner__acceptedShares}"),
            urwid.Text(f"Uptime: {self.miner._Miner__uptime}"),
            urwid.Text(f"Active: {'Yes' if self.miner._Miner__active else 'No'}"),
            urwid.Text(f"Last Reboot: {self.miner._Miner__lastRebooted.strftime('%-m-%-d %I:%M %p')}")
        ]
        left_column = urwid.Pile(self.details)
        
        # Calculate dialog size (80% of terminal)
        screen = urwid.raw_display.Screen()
        terminal_height = screen.get_cols_rows()[1]
        dialog_height = int(terminal_height * 0.8)  # Match the 80% from handle_miner_click
        
        # Calculate chart height
        # Subtract: 2 for outer box, 1 for title, 2 for inner boxes, 1 for chart header, 2 for button area
        self.chart_height = dialog_height - 8
        
        # Right column - Hashrate chart
        self.chart_pile = self.create_chart()
        # Remove the header text and use chart directly
        right_column = self.chart_pile
        
        # Combine columns
        columns = urwid.Columns([
            ('weight', 40, urwid.LineBox(left_column, title="Miner Details")),
            ('weight', 60, urwid.LineBox(right_column, title="Performance"))
        ])
        
        # Buttons
        reboot_btn = urwid.Button("Reboot", on_press=self._show_reboot_dialog)
        close_btn = urwid.Button("Close", on_press=self._close)
        reboot_btn = urwid.AttrMap(reboot_btn, 'button', focus_map='button_focus')
        close_btn = urwid.AttrMap(close_btn, 'button', focus_map='button_focus')
        
        buttons = urwid.GridFlow([reboot_btn, close_btn], 12, 3, 1, 'center')
        
        # Create a solid fill background for content area
        content_area = urwid.Frame(
            urwid.Filler(columns),
            footer=urwid.Pile([
                urwid.Divider(),
                buttons
            ])
        )
        
        # Add padding around everything
        padded = urwid.Padding(content_area, left=1, right=1)
        
        # Create the final box
        box = urwid.LineBox(padded, title=f"Miner Details - {self.miner._Miner__ip}")
        
        self._w = urwid.AttrMap(box, 'popup')

    def _update_dialog(self, loop, user_data):
        # Update the details
        self.details[2].set_text(f"Hashrate: {self.miner._Miner__hashrate} GH/s")
        self.details[3].set_text(f"Shares: {self.miner._Miner__acceptedShares}")
        self.details[4].set_text(f"Uptime: {self.miner._Miner__uptime}")
        self.details[5].set_text(f"Active: {'Yes' if self.miner._Miner__active else 'No'}")
        self.details[6].set_text(f"Last Reboot: {self.miner._Miner__lastRebooted.strftime('%-m-%-d %I:%M %p')}")
        
        # Update the chart
        new_chart = self.create_chart()
        self.chart_pile.contents = new_chart.contents
        
        # Schedule the next update
        self.loop.set_alarm_in(1, self._update_dialog)

    def create_chart(self):
        if not self.miner._Miner__hashrate_history:
            return urwid.Text("No history data available")
        
        chart_height = self.chart_height
        
        # Calculate chart width based on dialog size
        screen = urwid.raw_display.Screen()
        terminal_width = screen.get_cols_rows()[0]
        dialog_width = int(terminal_width * 0.8)  # 80% of terminal width
        performance_box_width = int((dialog_width * 0.6) - 4)  # 60% of dialog width minus borders
        label_width = 10  # Width for the hashrate labels
        chart_width = performance_box_width - label_width  # Removed the -2 to make chart 2 chars wider
        
        history = self.miner._Miner__hashrate_history
        
        if len(history) < 2:
            return urwid.Text("Collecting data...")
            
        # Convert GH/s to TH/s
        max_hashrate = max(h[1] for h in history) / 1000
        min_hashrate = min(h[1] for h in history) / 1000
        
        # Round to nearest 5
        max_hashrate = math.ceil(max_hashrate / 5) * 5
        min_hashrate = math.floor(min_hashrate / 5) * 5
        range_hashrate = max_hashrate - min_hashrate or 5  # Use 5 if range is 0
        
        # Create chart lines with Y-axis labels
        chart_lines = []
        for i in range(chart_height-1, -1, -1):
            # Calculate hashrate for this line
            hashrate = min_hashrate + (range_hashrate * (i / (chart_height-1)))
            # Format hashrate label (right-aligned in 7 chars)
            label = f"{int(hashrate):3d} TH/s │"
            
            # Create the chart line
            line = ""
            visible_history = history[-chart_width:] if len(history) > chart_width else history
            for _, rate in visible_history:
                rate_th = rate / 1000  # Convert to TH/s
                line += "█" if rate_th >= hashrate else " "
            
            # Pad line to exact width
            line = line.ljust(chart_width)
            
            # Create the row with fixed widths
            row = urwid.Columns([
                ('fixed', label_width, urwid.Text(('chart_label', label))),
                ('fixed', chart_width, urwid.Text(('chart_data', line)))
            ])
            chart_lines.append(row)
        
        # Create X-axis line
        x_axis = "└" + "─" * (label_width-2) + "┴" + "─" * chart_width
        chart_lines.append(urwid.Text(('chart_axis', x_axis)))
        
        # Add time labels
        if len(history) > 1:
            visible_start = history[-chart_width][0] if len(history) > chart_width else history[0][0]
            last_time = history[-1][0]
            time_label = f"{visible_start.strftime('%H:%M:%S')}".ljust(label_width-1)
            time_label += " " * (chart_width - 8)  # Adjust spacing between labels
            time_label += f"{last_time.strftime('%H:%M:%S')}"
            chart_lines.append(urwid.Text(('chart_label', time_label)))
        
        return urwid.Pile(chart_lines)
    
    def _show_reboot_dialog(self, button):
        dialog = ConfirmDialog(self.miner, self.loop, self.overlay)
        dialog_overlay = urwid.Overlay(
            dialog,
            self.overlay,
            'center', ('relative', 50),
            'middle', ('relative', 30)
        )
        self.loop.widget = dialog_overlay
    
    def _close(self, button):
        self.loop.widget = self.overlay

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
    
    main_content_with_style = urwid.AttrMap(pile, 'body')
    frame = urwid.Frame(main_content_with_style, header=header)
    
    # Create an overlay container
    overlay = urwid.Overlay(
        frame, urwid.SolidFill(' '),
        'center', ('relative', 100),
        'middle', ('relative', 100)
    )

    palette = [
        ('header', 'white,bold', 'dark red'),
        ('table_header', 'black,bold', 'white'),
        ('highlight_green', 'white', 'dark green'),
        ('highlight_red', 'white', 'dark red'),
        ('body', 'dark gray', 'light gray'),
        ('dialog', 'black', 'light gray'),
        ('button', 'black', 'light gray'),
        ('button_focus', 'white,bold', 'dark blue'),
        ('popup', 'black', 'white'),
        ('chart_label', 'dark blue', 'white'),
        ('chart_data', 'dark green', 'white'),
        ('chart_axis', 'dark blue', 'white'),
    ]

    # Use overlay instead of frame
    loop = urwid.MainLoop(overlay, palette, handle_mouse=True)
    loop.set_alarm_in(1, update_display, (header_text, miner_list, table, log_listbox, loop, overlay))
    loop.run()

if __name__ == "__main__":
    main()
