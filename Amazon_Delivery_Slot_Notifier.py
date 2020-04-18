__author__ = "Ojasvi Maleyvar"
__copyright__ = "Copyright 2020, The Corona Project"
__credits__ = ["Shivangi Gupta", "Vivek Gautam"]
__license__ = "GPL"
__version__ = "1.0.0"
__maintainer__ = "Ojasvi Maleyvar"
__email__ = "ojasvi.maleyvar@gmail.com; shivangigupta28@gmail.com"
__status__ = "Production"

import selenium
from selenium import webdriver
import pandas as pd
import numpy as np
import datetime
import time
import PySimpleGUI as sg
from bs4 import BeautifulSoup
from bs4 import Comment
import chromedriver_autoinstaller
import requests
from win32com.client import Dispatch
speak = Dispatch("SAPI.SpVoice")
import sys
import os
import os.path
import subprocess
import urllib.request
import urllib.error
import zipfile
import xml.etree.ElementTree as elemTree
import logging
import re
from io import BytesIO
import threading

#Chrome Driver Setup

def get_platform_architecture():
    if sys.platform.startswith('linux') and sys.maxsize > 2 ** 32:
        platform = 'linux'
        architecture = '64'
    elif sys.platform == 'darwin':
        platform = 'mac'
        architecture = '64'
    elif sys.platform.startswith('win'):
        platform = 'win'
        architecture = '32'
    else:
        raise RuntimeError('Could not determine chromedriver download URL for this platform.')
    return platform, architecture


def get_chrome_version():
    """
    :return: the version of chrome installed on client
    """
    platform, _ = get_platform_architecture()
    if platform == 'linux':
        with subprocess.Popen(['chromium-browser', '--version'], stdout=subprocess.PIPE) as proc:
            version = proc.stdout.read().decode('utf-8').replace('Chromium', '').strip()
    elif platform == 'mac':
        process = subprocess.Popen(['/Applications/Google Chrome.app/Contents/MacOS/Google Chrome', '--version'], stdout=subprocess.PIPE)
        version = process.communicate()[0].decode('UTF-8').replace('Google Chrome', '').strip()
    elif platform == 'win':
        process = subprocess.Popen(
            ['reg', 'query', 'HKEY_CURRENT_USER\\Software\\Google\\Chrome\\BLBeacon', '/v', 'version'],
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, stdin=subprocess.DEVNULL
        )
        version = process.communicate()[0].decode('UTF-8').strip().split()[-1]
    else:
        return
    return version

def get_matched_chromedriver_version(version):
    """
    :param version: the version of chrome
    :return: the version of chromedriver
    """
    doc = urllib.request.urlopen('https://chromedriver.storage.googleapis.com').read()
    root = elemTree.fromstring(doc)
    for k in root.iter('{http://doc.s3.amazonaws.com/2006-03-01}Key'):
        if k.text.find(get_major_version(version) + '.') == 0:
            return k.text.split('/')[0]
    return


def get_major_version(version):
    """
    :param version: the version of chrome
    :return: the major version of chrome
    """
    return version.split('.')[0]


def get_chromedriver_url(version):
    """
    Generates the download URL for current platform , architecture and the given version.
    Supports Linux, MacOS and Windows.
    :param version: chromedriver version string
    :return: Download URL for chromedriver
    """
    base_url = 'https://chromedriver.storage.googleapis.com/'
    platform, architecture = get_platform_architecture()
    return base_url + version + '/chromedriver_' + platform + architecture + '.zip'


def download_chromedriver():
    """
    Downloads, unzips and installs chromedriver.
    If a chromedriver binary is found in PATH it will be copied, otherwise downloaded.

    :param cwd: Flag indicating whether to download to current working directory
    :return: The file path of chromedriver
    """
    chrome_version = get_chrome_version()
    if not chrome_version:
        logging.debug('Chrome is not installed.')
        return
    chromedriver_version = get_matched_chromedriver_version(chrome_version)
    if not chromedriver_version:
        logging.debug('Can not find chromedriver for currently installed chrome version.')
        return
    major_version = get_major_version(chromedriver_version)

    
    url = get_chromedriver_url(version=chromedriver_version)
    try:
        response = urllib.request.urlopen(url)
        if response.getcode() != 200:
            raise urllib.error.URLError('Not Found')
    except urllib.error.URLError:
        raise RuntimeError(f'Failed to download chromedriver archive: {url}')
    archive = BytesIO(response.read())
    with zipfile.ZipFile(archive) as zip_file:
        zip_file.extract('chromedriver.exe')


def check_chrome():
    if os.path.isfile('chromedriver.exe'):
        print("Chrome Driver already exists")
        return str(os.getcwd())
    else:
        download_chromedriver()
        print("Downloaded Chrome Driver!")
        return str(os.getcwd())


def PostAlert(secret_tok, msg):
    url = 'https://pushmeapi.jagcesar.se'
    data='title=' + msg + '&token=' + secret_tok
    headers = {'Host': 'pushmeapi.jagcesar.se', 'User-Agent': 'curl/7.55.1', 'Accept': '*/*', \
               'Content-Length': str(len(data)), 'content-type': 'application/x-www-form-urlencoded'}
    r = requests.post(url, data, headers=headers)
    
    
def search_for_slots(driver, pushme_secret_tok, window):
    """
    A worker thread that communicates with the GUI through a global message variable
    This thread can block for as long as it wants and the GUI will not be affected
    """

    global message
    
    timer_running, counter = True, 0
    try:

        if "shipoptionselect" in driver.current_url:
            print("On the shipping page")
            delivery_slot_found = False
            driver.minimize_window()
            while delivery_slot_found == False:
                site_source_text = driver.page_source
                soup = BeautifulSoup(site_source_text)
                page_text = soup.get_text()
                if " AM " in page_text or " PM " in page_text or " AM" in page_text or " PM" in page_text:
                    print("Delivery slot found!")
                    delivery_slot_found = True

                    # Send Notification to iphone
                    pushme_msg = 'Delivery slot found! :) \n\n\n *Slots are not guaranteed'
                    PostAlert(pushme_secret_tok, pushme_msg)

                    sg.Popup('Delivery slot found! :)', 'Notification sent to your phone.')
                    driver.maximize_window()
                    n = 3
                    while n > 0:
                        speak.Speak("Delivery slot found! \
                                    A Notification has been sent to your phone.\
                                    Slots are not guaranteed!")
                        n -= 1 

                    window.close()


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
    sg.SetOptions(element_padding=(15,0))



    layout = [  
                [sg.Text('Please follow the below instructions:')],
                [sg.Text('1. Click the \'Launch Amazon Fresh\' button to begin!')],
                [sg.Text('2. Click the \'Notify Me!\' button ONLY when you are on the \'Schedule your order\' page.')],
                [sg.Text('\n\n\n')],
                [sg.Text('\n\n\n')],
                [sg.T(' ' * 5), sg.Button('Launch Amazon Fresh', button_color=('white', '#001480'), key='Launch Amazon Fresh'),
                 sg.Button('Notify Me!',button_color=('white', 'springgreen4'), key='Notify Me!'),
                 sg.Button('Exit', button_color=('white', 'firebrick3'), key='Exit')]
    ]
   

    # Create the Window
    window = sg.Window('Delivery Slot Finder', layout, icon='delivery-truck-icon.ico')
    window.Refresh()
        

    thread = None
    
    # --------------------- EVENT LOOP ---------------------
    while True:
        event, values = window.read()
        if event in (None, 'Exit'): # if user closes window or clicks cancel
            try:
                driver.quit()
                window.close()
            except:
                window.close()
            break

        elif event in 'Launch Amazon Fresh':
            print(event)
            chrome_driver_path = check_chrome()
            chrome_driver_path = chrome_driver_path + "\\chromedriver.exe"
            chromeOptions = webdriver.ChromeOptions()
            chromeOptions.add_experimental_option('useAutomationExtension', False)
            driver = webdriver.Chrome(executable_path=chrome_driver_path, options=chromeOptions, desired_capabilities=chromeOptions.to_capabilities())
            driver.get('https://www.amazon.com/alm/storefront?almBrandId=QW1hem9uIEZyZXNo&ref_=nav_cs_fresh')
        
        
        elif event in 'Notify Me!' and not thread:
            print(event)
            pushme_secret_tok = ""
            try:
                pushme_secret_tok = open("user_notification.txt", "r"); 
                pushme_secret_tok = pushme_secret_tok.read().strip()
                
            except:
                sg.Popup('Oops! User Notification Token file missing.', '\n',
                         'What do I do?',
                         'As simple as 1-2-3.',
                         '1. Download the \'Push Me\' app from iOS store and follow instructions to setup a token',
                         '2. Create text file called "user_notification.txt", paste the token in this file and save the file in the same folder as this tool',
                         '3. Re-Run the tool!')
                driver.quit()
                window.close()
                break
            
            thread = threading.Thread(target=search_for_slots, args=(driver, pushme_secret_tok, window), daemon=True)
            thread.start()
            
            if thread:
                if event in (None, 'Exit'): # if user closes window or clicks cancel
                    driver.quit()
                    window.close()
                    break
            else:
                driver.quit()
                window.close()
    
    window.close()
    

message = ''
if __name__ == '__main__':
    the_gui()
    print('Exiting Program')