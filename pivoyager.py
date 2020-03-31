# "i2c" needs to be enabled (e.g. via raspi-config)
# currently the pivoyager binary is needed; Defaults to /usr/local/bin/pivoyager
# https://www.omzlo.com/downloads/pivoyager.tar.gz
#
# Tutorial for installing the binary
# https://www.omzlo.com/articles/pivoyager-installation-and-tutorial
from threading import Thread
from subprocess import run, PIPE, DEVNULL
from time import sleep

from pwnagotchi.ui.components import LabeledValue
from pwnagotchi.ui.view import BLACK
import pwnagotchi.ui.fonts as fonts
import pwnagotchi.plugins as plugins
import pwnagotchi
import logging


class PiVoyager(plugins.Plugin):
    __author__ = 'ZTube'
    __version__ = '1.0.0'
    __license__ = 'GPL3'
    __description__ = 'A plugin for PiVoyager UPS compatibility'


    # Get the current status of the pivoyager
    def get_status(self):
        status = run([self.path, "status"], stdout=PIPE).stdout.decode().split("\n")
        stat_dict = {
                "stat": status[0].split(" ")[1:],
                "bat":  status[1].split(" ")[1],
                "vbat": status[2].split(" ")[1],
                "vref": status[3].split(" ")[1]
                }
        return stat_dict


    # Thread for shutting down on low battery voltage or a button press
    def check_status(self):
        while True:
            status = self.get_status()
            if(not "pg" in status["stat"]  and "low battery" in status["bat"]):
                logging.warn("Battery low! Shutting down")
                break
            elif("button" in status["stat"]):
                logging.warn("Button pressed! Shutting down")
                run([self.path, "clear", "button"])
                break
            sleep(self.refresh_time)
        run([self.path, "watchdog", "60"])
        pwnagotchi.shutdown()


    def on_loaded(self):
        # Initialise options
        self.path = self.options['path'] if 'path' in self.options else '/usr/local/bin/pivoyager'
        self.refresh_time = self.options['refresh_time'] if 'refresh_time' in self.options else 3

        self.status_thread = Thread(target=self.check_status, name="StatusThread")
        self.status_thread.start()

        status = self.get_status()
        if("inits" in status["stat"]):
            date = run([self.path, "date"], stdout=PIPE).stdout.decode()
            run(["date", "-s", date], stdout=DEVNULL)
            logging.info("pivoyager - updated local time from RTC")
        else:
            logging.warning("RTC not set could not sync local time")

        # enable power wakeup, enable alarm
        run([self.path, "enable", "power-wakeup"], stdout=DEVNULL)
        logging.info("pivoyager - enable power-wakeup")
        run([self.path, "alarm", "*-21-00-00"], stdout=DEVNULL)
        logging.info("pivoyager - enable alarm wakeup")
        logging.info("pivoyager ups plugin loaded.")


    def on_ui_setup(self, ui):
        ui.add_element('pivoyager', LabeledValue(color=BLACK, label=' ', value=' ', position=(192,84),
                                           label_font=fonts.Small, text_font=fonts.Small))

    def on_ui_update(self, ui):
        status = self.get_status()
        charge_mapping = {
                "charging":    "\u25AA",
                "discharging": "\u25AB"
                }
        ui.set('pivoyager', "{sbat} ups\n{voltage}".format(sbat=charge_mapping[status["bat"]], voltage=status["vbat"]))

    def on_internet_available(self, agent):
        if(not "inits" in self.get_status()["stat"]):
            # Update RTC if local time is ntp-synced and RTC is not initialised
            run([self.path, "date", "sync"])
            logging.info("pivoyager - update RTC from NTP")
			
