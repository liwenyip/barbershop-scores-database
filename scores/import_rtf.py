import re, string, csv, unicodedata, os, json, subprocess, pprint, pickle, decimal

try:
    from . extract_rtf import striprtf
except:
    from extract_rtf import striprtf

from decimal import *

# Make sure 70.25 is rounded up to 70.3
decimal.setcontext(decimal.BasicContext)

pp = pprint.PrettyPrinter(indent=4).pprint

PARTS = ['tenor', 'lead', 'bari', 'bass']
CATS = {
    'Music': 'm',
    'Performance': 'p',
    'Singing': 's',
    'CA': 'a'
}

ASSOCS = {
    'THE BRITISH ASSOCIATION OF BARBERSHOP SINGERS': 'BABS',
    'LADIES ASSOCIATION OF BRITISH BARBERSHOP SINGERS': 'LABBS',
}


######################################################################
### HELPERS
######################################################################

class DecimalEncoder(json.JSONEncoder):
    def default(self, o):
        if isinstance(o, decimal.Decimal):
            return float(o)
        return super(DecimalEncoder, self).default(o)


def getfiles(dirs, ext):
    """
    Returns a list of files with the specified extension
    :param dirs: list of directories to search in
    :param ext: extension to match
    :return: list of files
    """
    for d in dirs:
        for filename in os.listdir(d):
            if filename.endswith(ext):
                yield os.path.join(d, filename)


def change_ext(filename, ext):
    """
    Changes the extension of a filename
    :param filename:
    :param ext:
    :return:
    """
    return ('%s.%s' % (os.path.splitext(filename)[0], ext))


def parse_num(text):
    """
    Converts a string to an int or float
    :param text:
    :return:
    """
    try:
        return int(text.strip())
    except ValueError:
        return float(text.strip())


######################################################################
### HELPERS
######################################################################

def convert_all_rft2txt(dir):
    """
    Convert all files in a directory from rtf to plain text
    :param directory:
    :return:
    """
    for infile in getfiles([dir], 'rtf'):
        outfile = change_ext(infile, 'txt')
        try:
            with open(infile, 'rb') as f:
                t = striprtf(f.read())
            with open(outfile, 'w') as f:
                f.write(t)
        except Exception as e:
            print("error whilst parsing %s" % infile)
            print(e)
            pass


######################################################################
### HELPERS
######################################################################


def parse_contestant(text):
    """
    Parse text for one contestant, in this format:
    1: Cambridge Blues	Dear Old Girl	235	211	218
    	I Got Rhythm	211	206	210	1291	71.7
    	Previous (balanced):	440.0	440.0	411.0	2582.0
    :param text:
    :return: contestant dict
    """

    # Assemble the string containing rank, name, and members (usually split across several lines)
    # (Get all the text before the first tab on each line, and concatenate it)
    r = re.compile(r'^[^\t]+', re.MULTILINE)
    t = "".join(m.group(0) for m in r.finditer(text))

    # We sould now have a string in one of these formats:
    # 1: Cambridge Blues
    # 1: Hallmark Of Harmony (81)
    # 1: The Great Western Chorus Of Bristol  (Linda Corcoran) (52)
    # 1: RECKLESS  (Andy Foster, Duncan Whinyates, Dale Kynaston, Andy Funnell)

    # Extract rank and name (same for all types of contest)
    # Assumes contestant name doesn't contain any brackets
    m = re.match(r'(\d+): ([^\(]+)', t)
    contestant = {
        'rank': int(m.group(1)),
        'name': m.group(2).strip()
    }

    # Extract any text within brackets
    for m in re.finditer(r'\((.+?)\)', t):
        text_in_brackets = m.group(1).strip()
        try:
            # Check if it's the chorus size (an integer)
            contestant['size'] = int(text_in_brackets)
        except ValueError:
            # Split the string into seprate names.
            names = re.split(r'\s*(?: and |&|,|;|/)\s*', text_in_brackets)
            # 4 names = quartet members, less than 4 names = chorus director(s)
            if len(names) == 4:
                contestant['members'] = [{'part': PARTS[i], 'name': names[i]} for i in range(4)]
            else:
                contestant['members'] = [{'part': 'director', 'name': name} for name in names]

    # Get the strings containing the scores
    # (Get all the text after the first tab on each line)
    r = re.compile(r'\t(.+)$', re.MULTILINE)
    contestant['songs'] = [parse_song(m.group(1)) for m in r.finditer(text)]

    return contestant


def parse_song(text):
    """
    Extract song title and scores from a string in one of these formats:
    Dear Old Girl	235	211	218
    I Got Rhythm	211	206	210	1291	71.7
    Previous (balanced):	440.0	440.0	411.0	2582.0
    My Wife The Dancer	175	167	(- 13)	164	1015	56.4
    :param text:
    :return:
    """
    penalty = re.compile(r'\(- (\d+)\)')
    song = {'n': 1}

    # Split to a list of strings, then pop items off the list as it is parsed
    split = re.split('\t', text)

    # If the first item in the list is a number, it means there is no title
    if split[0].isdigit():
        print("warning - no song title")
        song['name'] = "unknown"
    else:
        song['name'] = split.pop(0)

    # Get the music score/penalty
    song['m'] = parse_num(split.pop(0))
    m = penalty.match(split[0])
    if m:
        song['mr'] = -parse_num(m.group(1))
        split.pop(0)

    # Get performance score/penalty
    song['p'] = parse_num(split.pop(0))
    m = penalty.match(split[0])
    if m:
        song['pr'] = -parse_num(m.group(1))
        split.pop(0)

    # Get singing score
    song['s'] = parse_num(split.pop(0))

    return song


def calculate_scores(contest):
    """
    Fill in the missing scores for a contest object, e.g. category total scores and song percentages
    :param contest: A contest object
    :return: The modified contest object
    """
    CATS = ('m', 'p', 's')

    # Very quick and dirty hack to deal with rolling panels - assuming only half the judges are on the panel at a time
    # Note str.find returns -1 if substring is not found
    # rolling_panel_factor = 1 if contest['raw_text'].find('Rolling Panel:') == -1 else 2

    # Calculate number of judges excluding administrators
    n_judges_by_cat = {cat: sum(1 for j in contest['judges'] if j['cat'] == cat) for cat in CATS}
    assert (n_judges_by_cat['m'] == n_judges_by_cat['p'] == n_judges_by_cat['s'])
    n_judges = sum(n_judges_by_cat.values())
    n_judges_per_cat = n_judges_by_cat['m']

    # Loop through contestants
    for contestant in contest['contestants']:

        # calculate total score for each song, and delete songs that have zero total score
        for song in contestant['songs']:
            song['tot_score'] = sum(song[cat] for cat in CATS)
            if song['tot_score'] == 0:
                print('warning - delete %s from %s' % (song, contestant))
        contestant['songs'] = [s for s in contestant['songs'] if s['tot_score'] > 0]

        # calculate percentage scores for each song
        for song in contestant['songs']:

            # Workaround to make sure that "Previous" scores in the BABS/LABBS scoresheets
            # are counted as two songs when calculating percentages
            song['n'] = 1 if (song['name'] is None or "Previous" not in song['name']) else 2

            # calculate song percentage score = total score / number of judges
            song['pc_score'] = float(round(Decimal(song['tot_score']) / song['n'] / n_judges, 1))

            # calculate song category percentage scores = category score / number of judges per cat
            for cat in CATS:
                song['%s_pc' % cat] = float(round(Decimal(song[cat]) / song['n'] / n_judges_per_cat, 1))

        # count the number of songs that the contestant sang (used for calculating contestant percentages
        contestant['n'] = sum(song['n'] for song in contestant['songs'])

        # calculate the category totals and percentages for each contestant
        for cat in CATS:
            contestant[cat] = sum(song[cat] for song in contestant['songs'])
            try:
                contestant['%s_pc' % cat] =  float(round(Decimal(contestant[cat]) / contestant['n'] / n_judges_per_cat, 1))
            except InvalidOperation:
                contestant['%s_pc' % cat] = 0

        # Calculate contestant total score and pc score
        contestant['tot_score'] = sum(song['tot_score'] for song in contestant['songs'])
        try:
            contestant['pc_score'] = float(round(Decimal(contestant['tot_score']) / contestant['n'] / n_judges, 1))
        except InvalidOperation:
            contestant['pc_score'] = 0


def txt_to_dict(filename):
    """
    Import text file to a contest dict
    :param filename:
    :return:
    """

    # Create new contest object
    contest = {
        'filename': filename
    }

    print('parsing %s' % filename)

    with open(filename, 'r') as f:
        plain_text = f.read()
    lines = plain_text.splitlines()


    # Get the association from the first line of text
    contest['assoc'] = ASSOCS[lines[0]]

    # Get the contest, location, and year from the third line of text
    r = re.compile(r'(?P<contest>.*)  -  (?P<location>.*): (?P<year>[\d/]*)')
    m = r.match(lines[2])
    for key in ('contest', 'location', 'year'):
        if len(m.group(key)) > 0:
            contest[key] = m.group(key)
        else:
            contest[key] = "UNKNOWN"
            print('warning - no %s' % key)

    # Chorus or quartet contest?
    if 'CHORUS' in contest['contest']:
        contest['type'] = 'c'
    elif 'QUARTET' in contest['contest']:
        contest['type'] = 'q'
    else:
        print('warning - unknown contest type')

    # Parse the contest date
    m = re.search('Contest date: (\d{2}/\d{2}/\d{4})', plain_text)
    if m:
        contest['date'] = m.group(1)
    else:
        contest['date'] = "01/01/1900"
        print('warning - no contest date')

    # Parse the judges
    contest['judges'] = []
    r = re.compile('(Music|Performance|Singing|CA): (.+)')
    for m in r.finditer(plain_text):
        # Convert 'Performance' to 'p' etc
        cat = CATS[m.group(1)]
        # Split the comma separated list of judges' names
        names = re.split(', *', m.group(2))
        # Add to list of judges
        for name in names:
            contest['judges'].append({'cat': cat, 'name': name.strip()})

    # Parse the contestants
    r = re.compile(r'(\d+:.*?)\n\tCategory', re.DOTALL)
    contest['contestants'] = [parse_contestant(m.group(1)) for m in r.finditer(plain_text)]

    # Calculate totals and percentages
    calculate_scores(contest)

    return contest


def txt_to_dicts(dir):
    for filename in getfiles([dir], 'txt'):
        yield txt_to_dict(filename)


##########################
# Do the running
##########################

if __name__ == "__main__":

    dir = r'C:\Users\Li-Wen Yip\Documents\GitHub\barbershop-scoresheet-scraper\BABS RTF'
    contests = []

    # Convert all the RTF files to TXT
    convert_all_rft2txt(dir)

    # Iterate through the text files
    for contest in txt_to_dicts(dir):

        # Save as pickle
        with open(change_ext(contest['filename'], 'pickle'), 'wb') as outfile:
            pickle.dump(contest, outfile)

        # Save as json
        with open(change_ext(contest['filename'], 'json'), 'w') as outfile:
            json.dump(contest, outfile, indent=2, cls=DecimalEncoder)

        # Append to the list of contests
        contests.append(contest)
