import re
import time
from datetime import datetime, timedelta

from ansi2html import Ansi2HTMLConverter

ansi_converter = Ansi2HTMLConverter()
ansi_pat = re.compile(r'\x1b[^m]*m')


def iso_date(date):
    return date.strftime("%Y-%m-%d %H:%M:%SZ")

    
def elapsed_time_string(total_minutes):
    hours = int(total_minutes / 60)
    
    if not hours:
        return '%d %s' % (total_minutes, 'minute' if total_minutes == 1 else 'minutes')
    
    minutes = total_minutes % (hours * 60)
        
    return '%d %s %d %s' % (hours, 'hour' if hours == 1 else 'hours',
                            minutes, 'minute' if minutes == 1 else 'minutes')


def ansi_to_html(ansi):
    html = ansi_converter.convert(ansi, full=False)
    return '<span class="ansi-container">' + html + ('</span>' * html.count('<span')) + '</span>'


def strip_ansi(text):
    return ansi_pat.sub('', text) if text else None
