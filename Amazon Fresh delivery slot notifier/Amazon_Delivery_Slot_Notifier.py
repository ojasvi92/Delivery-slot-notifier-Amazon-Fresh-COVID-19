__author__ = "Ojasvi Maleyvar <ojasvi.maleyvar@gmail.com>"
__credits__ = ["Shivangi Gupta", "Vivek Gautam"]
__license__ = "GPL"
__version__ = "1.0.0"

import logging
import os
import os.path
import re
import subprocess
import sys
import threading
import time
import xml.etree.ElementTree as elemTree
import zipfile
from io import BytesIO

import PySimpleGUI as sg
import requests
from bs4 import BeautifulSoup
from selenium import webdriver


# Chrome Driver Setup

def get_chrome_driver_filename():
    """
    Returns the filename of the binary for the current platform.
    :return: Binary filename
    """
    if sys.platform.startswith('win'):
        return 'chromedriver.exe'
    return 'chromedriver'


def get_chromedriver_url(version):
    """
    Returns the chrome drive url for the current platform.
    :return: Download URL for chromedriver
    """
    base_url = 'https://chromedriver.storage.googleapis.com/'
    platform, architecture = get_system_os()
    return base_url + version + '/chromedriver_' + platform + architecture + '.zip'


def get_system_os():
    """
    Returns the OS and architecture for the platform
    :return: platform and architecture bit
    """
    try:
        if sys.platform.startswith('linux') and sys.maxsize > 2 ** 32:
            platform = 'linux'
            architecture = '64'
        elif sys.platform == 'darwin':
            platform = 'mac'
            architecture = '64'
        elif sys.platform.startswith('win'):
            platform = 'win'
            architecture = '32'
        return platform, architecture
    except Exception as e:
        logging.error("Could not determine the System Operating System")
        logging.error(str(e))
        exit(1)


def check_version(binary, required_version):
    try:
        version = subprocess.check_output([binary, '-v'])
        version = re.match(r'.*?([\d.]+).*?', version.decode('utf-8'))[1]
        if version == required_version:
            return True
    except Exception:
        return False
    return False


def get_chrome_version():
    """
    :return: the version of chrome installed on client
    """
    try:
        platform, architecture = get_system_os()
        if platform == 'mac':
            process = subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'],
                                       stdout=subprocess.PIPE)
            version = process.communicate()[0].decode('UTF-8').replace('Google Chrome', '').strip()
        elif platform == 'win':
            process = subprocess.Popen(
                ['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'], \
                stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL)
            version = process.communicate()[0].decode('UTF-8').strip().split()[-1]
        elif platform == 'linux':
            with subprocess.Popen(['chromium-browser', '--version'], stdout=subprocess.PIPE) as proc:
                version = proc.stdout.read().decode('utf-8').replace('Chromium', '').strip()
        return version
    except Exception as e:
        logging.error("Could not get the Google Chrome Version")
        logging.error(str(e))
        exit(1)


def get_major_version(version):
    """
    :param version: the version of chrome
    :return: the major version of chrome
    """
    return version.split('.')[0]


def get_matched_chromedriver_version(version):
    """
    :param version: the version of chrome
    :return: the version of chromedriver
    """
    try:
        doc = requests.get('https://chromedriver.storage.googleapis.com')
        root = elemTree.fromstring(doc.content)
        for k in root.iter('{http://doc.s3.amazonaws.com/2006-03-01}Key'):
            if k.text.find(get_major_version(version) + '.') == 0:
                return k.text.split('/')[0]
        return
    except Exception as e:
        logging.error("Error in getting matched google chrome driver version")
        logging.error(str(e))
        exit(1)


def download_chrome_driver(cwd=False):
    """
    Downloads, unzips and installs chromedriver.
    If a chromedriver binary is found in PATH it will be copied, otherwise downloaded.
    :param cwd: Flag indicating whether to download to current working directory
    :return: The file path of chromedriver
    """
    try:
        chrome_version = get_chrome_version()
        if not chrome_version:
            logging.error("Chrome not installed. This application works only with Google Chrome")
            exit(1)
        chrome_driver_version = get_matched_chromedriver_version(chrome_version)
        if not chrome_driver_version:
            logging.error("Cannot find chromedriver for currently installed chrome version")
            exit(1)
        major_version = get_major_version(chrome_driver_version)
        if cwd:
            chrome_driver_dir = os.path.join(
                os.path.abspath(os.getcwd()),
                major_version
            )
        else:
            chrome_driver_dir = os.path.join(
                os.path.abspath(os.path.dirname(__file__)),
                major_version
            )

        chrome_driver_filename = get_chrome_driver_filename()
        chrome_driver_filepath = os.path.join(chrome_driver_dir, chrome_driver_filename)
        if not os.path.isfile(chrome_driver_filepath) or \
                not check_version(chrome_driver_filepath, chrome_driver_version):
            logging.info('Downloading chromedriver ({chrome_driver_version})...')
            if not os.path.isdir(chrome_driver_dir):
                os.mkdir(chrome_driver_dir)
            download_endpoint = get_chromedriver_url(version=chrome_driver_version)
            try:
                response = requests.get(download_endpoint)
                if response.status_code != 200:
                    logging.error("Download URL not found")
                    exit(1)
            except Exception as e:
                logging.error('Failed to download chromedriver archive: {download_endpoint}')
            archive = BytesIO(response.content)
            with zipfile.ZipFile(archive) as zip_file:
                zip_file.extract(chrome_driver_filename, chrome_driver_dir)
        else:
            logging.info("Chrome Driver is already installed.")
        if not os.access(chrome_driver_filepath, os.X_OK):
            os.chmod(chrome_driver_filepath, 0o744)

        return chrome_driver_filepath

    except Exception as e:
        logging.error("Unable to download the Google Chrome Driver")
        logging.error(str(e))
        exit(1)


def PostAlert(PUSHuser, PUSHkey, pushme_msg):
    PUSHtitle = "Delivery Slot Notifier"
    url = 'https://api.pushmealert.com'
    myobj = {'user': PUSHuser, 'key': PUSHkey, 'title': PUSHtitle, 'message': pushme_msg}
    r = requests.post(url, data=myobj)


def search_for_slots(driver, PUSHuser, PUSHkey, window, platform):
    """
    A worker thread that communicates with the GUI through a global message variable
    This thread can block for as long as it wants and the GUI will not be affected
    """

    global message

    try:
        if "shipoptionselect" in driver.current_url:
            delivery_slot_found = False
            driver.minimize_window()
            while not delivery_slot_found:
                site_source_text = driver.page_source
                soup = BeautifulSoup(site_source_text, 'html.parser')
                page_text = soup.get_text()
                if " AM " in page_text or " PM " in page_text or " AM" in page_text or " PM" in page_text:
                    print("Delivery slot found!")
                    delivery_slot_found = True

                    # Send Notification to iphone
                    pushme_msg = 'Delivery slot found! :) (Please book quickly as slots are not guaranteed)'
                    PostAlert(PUSHuser, PUSHkey, pushme_msg)

                    sg.Popup('Delivery slot found! :)', 'Notification sent to your phone.')
                    driver.maximize_window()
                    if platform == "win":
                        from win32com.client import Dispatch
                        speak = Dispatch("SAPI.SpVoice")
                        n = 3
                        while n > 0:
                            speak.Speak("Delivery slot found! A Notification has been sent to your phone. Slots are not guaranteed!")
                            n -= 1
                    if platform == "mac":
                        n = 3
                        while n > 0:
                            os.system("say 'Delivery slot found! A Notification has been sent to your phone. Slots are not guaranteed!'")
                            n -= 1

                    if platform == "linux":
                        n = 3
                        while n > 0:
                            os.system("spd-say 'Delivery slot found! A Notification has been sent to your phone. Slots are not guaranteed!'")
                            n -= 1

                else:
                    time.sleep(10)
                    driver.refresh()

        else:
            sg.Popup("Encountered an Error!",
                     "Click the \'Notify Me!\' button ONLY when you are on the \'Schedule your order\' page.",
                     "Please try again.")

            driver.quit()
            window.close()

    except:
        driver.quit()
        window.close()

    message = f'*** Operation Done ***'


def the_gui():
    """
    Starts and executes the GUI
    Reads data from a global variable and displays
    Returns when the user exits / closes the window
    """
    global message, progress

    sg.theme('DarkAmber')

    sg.ChangeLookAndFeel('Dark')
    sg.SetOptions(element_padding=(15, 0))

    layout = [
        [sg.Text('Please follow the below instructions:')],
        [sg.Text('1. Click the \'Launch Amazon Fresh\' button to begin!')],
        [sg.Text('2. Click the \'Notify Me!\' button ONLY when you are on the \'Schedule your order\' page.')],
        [sg.Text('\n\n\n')],
        [sg.Text('\n\n\n')],
        [sg.T(' ' * 5), sg.Button('Launch Amazon Fresh', button_color=('white', '#001480'), key='Launch Amazon Fresh'),
         sg.Button('Notify Me!', button_color=('white', 'springgreen4'), key='Notify Me!'),
         sg.Button('Exit', button_color=('white', 'firebrick3'), key='Exit')]
    ]

    icon = b'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'

    # Create the Window
    window = sg.Window('Delivery Slot Finder', layout, icon=icon)
    window.Refresh()

    thread = None

    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read()
        if event in (None, 'Exit'):  # if user closes window or clicks cancel
            try:
                driver.quit()
                window.close()
            except:
                window.close()
            break

        elif event in 'Launch Amazon Fresh':

            chrome_driver_filepath = download_chrome_driver(cwd=True)
            chrome_driver_dir = os.path.dirname(chrome_driver_filepath)

            chromeOptions = webdriver.ChromeOptions()
            chromeOptions.add_experimental_option('useAutomationExtension', False)
            driver = webdriver.Chrome(executable_path=chrome_driver_dir + '/chromedriver', options=chromeOptions,
                                      desired_capabilities=chromeOptions.to_capabilities())
            driver.get('https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo&ref_=nav_cs_fresh')


        elif event in 'Notify Me!' and not thread:
            PUSHuser = ""
            PUSHkey = ""
            try:
                platform, architecture = get_system_os()
                if platform == "mac" or platform == "linux":
                    exec_path = sys.executable
                    exec_path = exec_path.strip("Amazon_Delivery_Slot_Notifier")
                    user_notification_file = exec_path + "/user_notification.txt"
                elif platform == "win":
                    user_notification_file = "user_notification.txt"

                with open(user_notification_file, "r") as infile:
                    file_data = infile.readlines()
                    for i in file_data:
                        if i.startswith('user'):
                            PUSHuser = i.split(":")[1].strip()
                        elif i.startswith('key'):
                            PUSHkey = i.split(":")[1].strip()

            except:
                sg.Popup('Oops! User Notification Token file missing.', '\n',
                         'What do I do?',
                         'As simple as 1-2-3.',
                         '1. Download the \'PushMeAlert\' app from App store, Register with your phone number, Save the user & key token from settings page',
                         '2. Create text file called "user_notification.txt", paste the user and key token in this file and save the file in the same folder as this tool',
                         '3. Re-Run the tool!')
                driver.quit()
                window.close()
                break
            platform, architecture = get_system_os()
            thread = threading.Thread(target=search_for_slots, args=(driver, PUSHuser, PUSHkey, window, platform),
                                      daemon=True)
            thread.start()

            if thread:
                if event in (None, 'Exit'):  # if user closes window or clicks cancel
                    driver.quit()
                    window.close()
                    break
            else:
                #driver.quit()
                window.close()

    window.close()


message = ''
if __name__ == '__main__':
    the_gui()
    print('Exiting Program')
