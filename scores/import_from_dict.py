from datetime import datetime
from .models import *

###############################################################
# Functions to manipulate a contest dict
###############################################################


def calculate_scores(contest):
    """
    Fill in the missing scores for a contest object, e.g. category total scores and song percentages
    :param contest: A contest object
    :return: The modified contest object
    """
    CATS = ('m', 'p', 's')

    # Very quick and dirty hack to deal with rolling panels - assuming only half the judges are on the panel at a time
    # Note str.find returns -1 if substring is not found
    rolling_panel_factor = 1 if contest['raw_text'].find('Rolling Panel:') == -1 else 2

    # Calculate number of judges excluding administrators
    n_judges_by_cat = {cat: sum(1 / rolling_panel_factor for j in contest['judges'] if j['cat'] == cat) for cat in CATS}
    n_judges = sum(n_judges_by_cat.values())

    for contestant in contest['contestants']:

        # calculate the total score, total percentage, and category percentages for each song
        for song in contestant['songs']:

            # Workaround to make sure that "Previous" scores in the BABS/LABBS scoresheets
            # are counted as two songs when calculating percentages
            song['n'] = 2 if song['name'].find("Previous") >= 0 else 1

            # calculate song total score = sum of category scores
            song['tot_score'] = sum(song[cat] for cat in CATS)

            # calculate song percentage score = total score / number of judges
            song['pc_score'] = round(song['tot_score'] / n_judges / song['n'], 1)

            # calculate song category percentage scores = category score / number of judges
            for cat in CATS:
                song['%s_pc' % cat] = round(song[cat] / n_judges_by_cat[cat] / song['n'], 1)

        # count the number of songs that the contestant sang (used for calculating contestant percentages
        contestant['n'] = sum(song['n'] for song in contestant['songs'])

        # calculate the category totals and percentages for each contestant
        for cat in CATS:
            contestant[cat] = sum(song[cat] for song in contestant['songs'])
            contestant['%s_pc' % cat] = round(contestant[cat] / n_judges_by_cat[cat] / contestant['n'], 1)

        # check the contestant total score and percentage is correct
        tot_score = sum(song['tot_score'] for song in contestant['songs'])
        assert int(contestant['tot_score']) == tot_score, "%s <> %s" % (contestant['tot_score'],  tot_score)
        pc_score = round(contestant['tot_score'] / n_judges / contestant['n'], 1)
        #assert contestant['pc_score'] == pc_score, "%s <> %s" % (contestant['pc_score'],  pc_score)


def prepare_for_import(contest):
    """
    Prepare a contest dict for import
    :param contest:
    :return:
    """
    # fix the date field
    try:
        contest['date'] = datetime.strptime(contest['date'], '%d/%m/%Y')
    except ValueError:
        contest['date'] = datetime.strptime(contest['date'], '%d %b %Y')

    # shorten assoc field
    contest['assoc'] = {
        'THE BRITISH ASSOCIATION OF BARBERSHOP SINGERS': 'BABS',
        'LADIES ASSOCIATION OF BRITISH BARBERSHOP SINGERS': 'LABBS',
    }[contest['assoc']]

    # calculate missing fields
    calculate_scores(contest)

    return contest


###############################################################
# Functions to import a contest dict to database
###############################################################


def import_contest_from_dict(d):

    # construct top-level object (Contest) using the top-level dict (excluding nested dicts)
    contest, contest_created = Contest.objects.get_or_create(
        **{k: v for k, v in d.items() if k not in ('judges', 'contestants', 'url')},
        contesturl__url=d['url'],
    )
    print("%s contest %s" % ("created" if contest_created else "got", contest))

    # if the contest already existed, don't import it
    if not contest_created:
        print("CONTEST NOT IMPORTED")
        return

    # add url
    url, created = contest.contesturl_set.get_or_create(url=d['url'])

    # add judges
    print("adding %s judges" % len(d['judges']))
    for j in d.get('judges', []):
        # create person if they don't exist
        person, created = Person.objects.get_or_create(
            name__iexact=j['name'],
            defaults={'name': j['name']},
        )
        print("%s person %s" % ("created" if created else "got", person))
        # get the canonical name if this name is an alias
        while person.alias_of:
            print("following judge alias")
            person = Person.objects.get(id=person.alias_of)
        # create the (record of) the person's appearance as a judge
        contest.judge_set.create(
            person=person,
            **j,
        )

    # add contestants
    print("adding %s contestants" % len(d['contestants']))
    for c in d.get('contestants', []):
        # create contestant if they don't exist
        contestant, created = Contestant.objects.get_or_create(
            name__iexact=c['name'],
            assoc=d['assoc'],
            type=d['type'],
            defaults={'name': c['name']},
        )
        print("%s contestant %s" % ("created" if created else "got", contestant))
        # get the canonical name if this name is an alias
        while contestant.alias_of:
            print("following contestant alias")
            contestant = Contestant.objects.get(id=contestant.alias_of)
        # create the (record of) the contestant's appearance in this contest
        contestantapp = contest.contestantapp_set.create(
            contestant=contestant,
            **{k: v for k, v in c.items() if k not in ('members', 'songs')},
        )

        # add songs
        for s in c.get('songs', []):
            # create song if it doesn't exist
            song, created = Song.objects.get_or_create(
                name__iexact=s['name'],
                defaults={'name': s['name']},
            )
            print("%s song %s" % ("created" if created else "got", song))
            # get the canonical name if this name is an alias
            while song.alias_of:
                print("following song alias")
                song = Song.objects.get(id=song.alias_of)
            # create the (record of) the song's appearance during this contestant's appearance
            contestantapp.songapp_set.create(
                song=song,
                **s,
            )

        # add members (singers or directors)
        for m in c.get('members', []):
            # create person if they don't exist
            person, created = Person.objects.get_or_create(
                name__iexact=m['name'],
                defaults={'name': m['name']},
            )
            print("%s person %s" % ("created" if created else "got", person))
            # get the canonical name if this name is an alias
            while person.alias_of:
                print("following member alias")
                person = Person.objects.get(id=person.alias_of)
            # create the (record of) the person's appearance as a member of this contestant
            contestantapp.member_set.create(
                person=person,
                **m,
            )

###############################################################
# Functions to merge two contests
###############################################################

    # If we've added more contestants to an existing contest, we need to recalculate the overall rank
    if not contest_created:
        rank, tie_score = 0, 0
        for contestantapp in contest.contestantapp_set.all().order_by('-tot_score'):
            rank += 1
            contestantapp.rank = rank - (1 if contestantapp.tot_score == tie_score else 0)
            contestantapp.save()
            tie_score = contestantapp.tot_score

        # add stream rank
        """
        streamrank = contestantapp.streamrank_set.get_or_create(
            stream=d['stream'],
            defaults={'rank': c['rank']},
        )
        """
