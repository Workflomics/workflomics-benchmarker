
import re


def natural_keys(text):
    '''
    Function to convert text to lower case and digits to integer
    '''
    return [int(c) if c.isdigit() else c.lower() for c in re.split('(\d+)', text)]