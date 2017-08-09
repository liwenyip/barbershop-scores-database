from datetime import datetime
from bs4 import BeautifulSoup
from urllib.request import urlopen, urlretrieve
from urllib.parse import urlparse, urljoin
import re
from django.http import HttpResponseRedirect, HttpResponse
from PyPDF2 import PdfFileWriter, PdfFileReader
import re, string, csv, unicodedata, os, json, subprocess, pprint

###############################################################
# PDF Handling Functions
###############################################################


def pdftotext(url):
    """
    Convert PDF file to text
    :param url: url of pdf file
    :return: text as string
    """
    PDFTOTEXT = r'C:\Program Files\Xpdf\bin64\pdftotext.exe'
    # download the pdf file
    filename, headers = urlretrieve(url)
    textfilename = filename + ".txt"
    # convert the pdf file to a text file
    subprocess.run([PDFTOTEXT, '-raw', filename, textfilename])
    # read the text file
    with open(textfilename) as f:
        text = f.read()
    # clean up
    os.unlink(textfilename)
    os.unlink(filename)         # NB if URL points to a local file, it will be deleted!!!
    # return the text
    return text


###############################################################
# Text parsing helpers
###############################################################


def fix_text(text):
    """
    Strip newlines, fix hyphenated names, and trim whitespace
    :param text:
    :return: int, float, or string
    """
    # Return None if we've not been given a string
    if not isinstance(text,str):
        return None

    # Trim whitespace
    text = text.strip()

    # Try converting to an int or float:
    try:
        return int(text)
    except ValueError:
        try:
            return float(text)
        except ValueError:
            pass

    # strip newlines
    text = re.sub(r"\s*\n\s*", " ", text)
    # fix hyphenated names that have broken
    text = re.sub(r"(\w)\s*\-\s*(\w)", r"\1-\2", text)
    # trim whitespace
    return text


###############################################################
# Generic Regex Components
###############################################################

# \n889\n
# \n1384\n
# \n1384.0\n
TOT_SCORE = r"(?P<tot_score>\d{3,4})(?:\.\d)?\s*"
PREV_TOT_SCORE = r"(?P<prev_tot_score>\d{3,4})(?:\.\d)?\s*"

# Stars Fell On Alabama\nFly Me To The Moon\n
SONGS = "".join(r"(?P<%s>[^\n]+)\s" % key for key in ('name1', 'name2'))

# 228\n223\n229\n225\n231\n227\n
# 252250247\n244\n247243111\n
CAT_SCORES = "".join(r"(?P<%s>\d{3})\s*" % key for key in ('m1', 'm2', 'p1', 'p2', 's1', 's2'))

# Previous (balanced):\n459.0\n458.0\n461.0\n
PREV_SCORES = r"(?P<nameprev>Previous) \([Bb]alanced\):\s?" + "".join(r"(?P<%s>\d{3})\.\d\s*" % key for key in ('mprev', 'pprev', 'sprev'))

# 1\n1\n1\nCategory rankings:\n
# 111\nCategory rankings:\n
CAT_RANKS = "".join(r"(?P<%s>\d{1,2})\s*" % key for key in ('rank_m', 'rank_p', 'rank_s')) + "Category [Rr]ankings:\n"

# 1:
RANK = r"(?P<rank>\d+):\s*"

# Chorus/Quartet name
NAME = r"(?P<name>[^\(]+?)\s*" # Assumes name is followed by a (

# (Sarah Hicks, Gill \nIrwin, Julie Robinson,  Monica \nFunnell)
SINGERS = r"\((?P<tenor>[^\.,]+?)[\.,]\s*(?P<lead>[^\.,]+?)[\.,]\s*(?P<bari>[^\.,]+?)[\.,]\s*(?P<bass>[^\.,]+?)[\.,]?\)\s*"
SINGERS = r"(?:%s)?" % SINGERS # Some quartets don't give a list of singers

# (Jo Braham)
DIRECTOR = r"\((?P<director>[^\.,]+?)\)\s*"

# (47)\n
SIZE = r"\((?P<size>\d{1,3})\)\s?"

# 82.3
PC_SCORE = r"(?P<pc_score>\d\d\.\d)"


###############################################################
# Text extraction functions
###############################################################


def get_contest_details(text):
    """
    Extract contest details from text
    :param text: text extracted from pdf file using pdftotext
    :return: dict containing contest details
    """
    # (OFFICIAL CONTEST RESULT\n)? and (\d{2} \w{3} 20\d{2}) are unique to the 2009 files
    r = r'^(?P<assoc>.*)\n(OFFICIAL CONTEST RESULT\n)?(?P<contest>.*?)(?:\((?P<stream>[INYS]).*\))? - (?P<location>.*): (?P<year>.*)\n[\w\W]+(?P<date>\d{2}/\d{2}/20\d{2}|\d{2} \w{3} 20\d{2})'
    m = re.compile(r).search(text)
    return {key: m.group(key) for key in ('assoc', 'contest', 'stream', 'location', 'year', 'date')}


def get_judges(text):
    """
    Extract judges' details from text
    :param text: text extracted from pdf file using pdftotext
    :return: dict containing judges' details
    """
    keys = ('m', 'p', 's', 'a')
    r = r'Music:(?: Rolling Panel:-)?(?P<m>.*)\n?'
    r += r'(?:Performance|Presentation):(?: Rolling Panel:-)?(?P<p>.*)\n?'
    r += r'Singing:(?: Rolling Panel:-)?(?P<s>.*)\n?'
    r += r'(?:Admin|CA|CoJ):(?: Rolling Panel:-)?(?P<a>.*?)(?:\n|Signed)'
    m = re.compile(r, re.DOTALL).search(text)
    judges = []
    for key in keys:
        judges.extend([{'cat': key, 'name': fix_text(n.strip())} for n in m.group(key).split(',')])
    return judges


def get_contestants(text, keys, song_keys, member_keys, regex):
    """
    Get contestant details from text
    :param text: text extracted from pdf file using pdftotext
    :param keys:
    :param song_keys:
    :param member_keys:
    :param regex:
    :return: dict containing contestant details
    """
    l = []
    for m in re.compile(regex).finditer(text):
        x = {key: fix_text(m.group(key)) for key in keys}
        x['songs'] = [{key: fix_text(m.group(key + str(n))) for key in ('name', 'm', 's', 'p')} for n in song_keys]
        x['members'] = [ {'part': key, 'name': fix_text(m.group(key))} for key in member_keys]

        # Split joint directors in two TODO: test this to make sure it works
        if 'director' in member_keys:
            directors = fix_text(m.group('director'))
            if directors.find('/'):
                x['members'] = [ {'part': 'director', 'name': director } for director in directors.split('/') ]
            elif directors.find(' and '):
                x['members'] = [ {'part': 'director', 'name': director } for director in directors.split(' and ') ]

        l.append(x)
    return l


def get_scoresheet_format(text):
    if re.search('CHORUS', text):
        return 'c' # chorus
    elif re.search(r"Previous \([Bb]alanced\)", text):
        return 'qf' # quartet final
    else:
        return 'q' # quartet








def get_contest_dict_from_url(url):
    # extract the text from the pdf
    text = pdftotext(url)

    # parse text to extract contest
    contest = get_contest_details(text)

    # save the raw text
    contest['raw_text'] = text

    # extract some more details
    contest['url'] = url
    contest['judges'] = get_judges(text)
    contest['type'] = 'c' if re.search('CHORUS', text) else 'q' if re.search('QUARTET|NATIONAL GOLD MEDALLISTS', text) else '?'

    # parse text to extract contestant details - depends on scoresheet format
    format = get_scoresheet_format(text)
    if format == 'c': # chorus
        keys = ('tot_score', 'rank_m', 'rank_s', 'rank_p', 'rank', 'name', 'size', 'pc_score')
        r = TOT_SCORE + SONGS + CAT_SCORES + CAT_RANKS + RANK + NAME + DIRECTOR + SIZE + PC_SCORE
    elif format == 'qf': # quartet final
        keys = ('tot_score', 'rank_m', 'rank_s', 'rank_p', 'rank', 'name', 'pc_score')
        r = PREV_TOT_SCORE + TOT_SCORE + SONGS + CAT_SCORES + PREV_SCORES + CAT_RANKS + RANK + NAME + SINGERS + PC_SCORE
    else: # quartet semi-final, prelims, or mixed
        keys = ('tot_score', 'rank_m', 'rank_s', 'rank_p', 'rank', 'name', 'pc_score')
        r = TOT_SCORE + SONGS + CAT_SCORES + CAT_RANKS + RANK + NAME + SINGERS + PC_SCORE
    member_keys = ('director',) if format == 'c' else ('tenor', 'lead', 'bari', 'bass')
    song_keys = (1, 2, 'prev') if format == 'qf' else (1,2)
    contest['contestants'] = get_contestants(text, keys, song_keys, member_keys, r)

    # return the contest dict
    return contest



