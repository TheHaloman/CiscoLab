#!/usr/bin/env python
# """Module docstring."""

#Imports
from netmiko import ConnectHandler
import csv
import logging
import datetime
import multiprocessing as mp
import difflib
import filecmp
import sys
import os

#Module 'Global' variables
DEVICE_LIST = 'devices.csv'
BACKUP_DIR_PATH = './backups'

def enable_logging():
    # This function enables netmiko logging for reference

    logging.basicConfig(filename='test.log', level=logging.DEBUG)
    logger = logging.getLogger("netmiko")

def get_devices_from_file(device_file):
    # This function takes a CSV file with inventory and creates a python list of dictionaries out of it
    # Each disctionary contains information about a single device

    # creating empty structures
    device_list = list()
    device = dict()

    # reading a CSV file with ',' as a delimeter
    with open(device_file, 'r') as f:
        reader = csv.DictReader(f, delimiter=',')

        # every device represented by single row which is a dictionary object with keys equal to column names.
        for row in reader:
            device_list.append(row)

    #print ("Список устройств получен")

    # returning a list of dictionaries
    return device_list

def get_current_date_and_time():
    # This function returns the current date and time
    now = datetime.datetime.now()

    #print("Временная метка получена")

    # Returning a formatted date string
    # Format: yyyy_mm_dd-hh_mm_ss
    return now.strftime("%Y_%m_%d-%H_%M_%S")

def connect_to_device(device):
    # This function opens a connection to the device using Netmiko
    # Requires a device dictionary as an input

    # Since there is a 'hostname' key, this dictionary can't be used as is
    connection = ConnectHandler(
        host = device['ip'],
        username = device['username'],
        password=device['password'],
        device_type=device['device_type'],
        secret=device['secret']
    )

    #print ('Открыто соединие с устройством:  '+device['ip'])

    # returns a "connection" object
    return connection

def disconnect_from_device(connection, hostname):
    #This function terminates the connection to the device

    connection.disconnect()
    #print ('Соединение с устройством {} сброшено'.format(hostname))

def get_backup_file_path(hostname,timestamp):
    # This function creates a backup file name (a string)
    # backup file path structure is hostname/hostname-yyyy_mm_dd-hh_mm

    # checking if backup directory exists for the device, creating it if not present
    if not os.path.exists(os.path.join(BACKUP_DIR_PATH, hostname)):
        os.makedirs(os.path.join(BACKUP_DIR_PATH, hostname))
    
    # Merging a string to form a full backup file name
    backup_file_path = os.path.join(BACKUP_DIR_PATH, hostname, '{}-{}.txt'.format(hostname, timestamp))

    # returning backup file path
    return backup_file_path

def create_backup(connection, backup_file_path, hostname):
    # This function pulls running configuration from a device and writes it to the backup file
    # Requires connection object, backup file path and a device hostname as an input

    try:
        # sending a CLI command using Netmiko and printing an output
        connection.enable()
        output = connection.send_command('sh run')

        # creating a backup file and writing command output to it
        with open(backup_file_path, 'w') as file:
            file.write(output)
        #print("Создание резервной копии конфигурации устройства " + hostname + " выполнено!")

        # if successfully done
        return True

    except Error:
        # if there was an error
        #print('Ошибка! Невозможно создать рещервную копию конфигурации устройства  ' + hostname)
        return False

def check_cdp(connection):
    
    output = connection.send_command('sh cdp neigh')
    
    if output.find('CDP is not enabled')>-1:
        return('CDP off,0 peers')
    else:
        output = output[output.find("Device ID"):]
        output = output.split('\n')
        return('CDP on,{} peers'.format(len(output) - 1))

def npe_check(connection):
    
    output = connection.send_command('show version')
    output = output[:output.find("\n")]

    if output.find("NPE") > -1 :
        return "NPE"
    else:
        return "PE"
        
def model_check(connection):
    
    output = connection.send_command('show inventory')
    output = output[output.find('DESCR: "')+8:]
    output = output[:output.find('"')]
    return(output)
    
def ios_check(connection):
     
    output = connection.send_command('show version')
    
    if (output.find('IOS XE Version') > -1):
        output = output[output.find('IOS XE Version')+14:]
        output = output[:output.find('\n')]
        output = output.strip()
    elif (output.find('Version')>-1):
        output = output[output.find('Version')+7:]
        output = output[:output.find(',')]
        output = output.strip()
    else:
        output = 'version undefined'
    return output   


def sync_time(connection):
    
    output = connection.send_command('ping 192.168.100.4')
    
    if(output.find('!')>-1):
    
        output = connection.send_config_set('ntp server 192.168.100.4')
        output = connection.send_config_set('clock timezone GMT 0')
        return 'Clock in Sync'
    
    else:
    
        return "Clock not in Sync"


def process_target(device,timestamp):
    
    device_info = device['hostname']
    connection = connect_to_device(device)
    device_info = device_info + '|' + model_check(connection)
    device_info = device_info + '|' + ios_check(connection)
    backup_file_path = get_backup_file_path(device['hostname'], timestamp)
    backup_result = create_backup(connection, backup_file_path, device['hostname'])
    device_info = device_info + '|' + npe_check(connection)
    device_info = device_info + '|' + check_cdp(connection)
    device_info = device_info + '|' + sync_time(connection)
    disconnect_from_device(connection, device['hostname'])
    print(device_info)


def main(*args):
    
    enable_logging()

    timestamp = get_current_date_and_time()
    
    device_list = get_devices_from_file(DEVICE_LIST)

    processes = list()
    
    print("Скрипт выполняется - подождите немного.\n")

    with mp.Pool(4) as pool:
        # Starting several processes...
        for device in device_list:
            processes.append(pool.apply_async(process_target, args=(device,timestamp)))
        # Waiting for results...
        for process in processes:
            process.get()


if __name__ == '__main__':
    # checking if we run independently
    _, *script_args = sys.argv
    
    # the execution starts here
    main(*script_args)







