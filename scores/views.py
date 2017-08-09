from django.shortcuts import get_object_or_404, render
from django.http import HttpResponseRedirect, HttpResponse
from django.urls import reverse
from django.views import generic
from django.utils import timezone
from collections import defaultdict
from django.db.models import Count, Min, Max, Avg, Case, When, Sum, IntegerField
from dal import autocomplete

from .scrape_pdf import *
from .models import *
from .forms import *
from .import_from_dict import *

import time, json, pprint

pf = pprint.PrettyPrinter(indent=4, width=120).pformat


class PersonAutocomplete(autocomplete.Select2QuerySetView):
    model = Person
    create_field = 'name'

    # Not needed because the default get_queryset() function just happens to do exactly the same thing
    #def get_queryset(self):
    #    return Person.objects.filter(name__icontains=self.q) if self.q else Person.objects.all()

    def has_add_permission(self, request):
        return True

class ContestList(generic.ListView):
    model = Contest


class ContestView(generic.DetailView):
    model = Contest


class ContestantList(generic.ListView):
    model = Contestant


class ContestantView(generic.DetailView):
    model = Contestant


def agg_pc(agg_function, type):
    """
    For conditionally aggregating pc_score
    Refer https://docs.djangoproject.com/en/1.11/ref/models/conditional-expressions/#conditional-aggregation
    :param agg_function: Min, Avg, or Max
    :param type: 'q' or 'c'
    :return:
    """
    return agg_function(
        Case(
            When(
                songapp__contestantapp__contest__type=type,
                then='songapp__pc_score',
            )
        )
    )


def count_by_type(type):
    """
    For conditionally counting songs
    Refer https://docs.djangoproject.com/en/1.11/ref/models/conditional-expressions/#conditional-aggregation
    :param type: 'q' or 'c'
    :return:
    """
    return Sum(
        Case(
            When(
                songapp__contestantapp__contest__type=type,
                then=1
            ),
            output_field=IntegerField(),
        )
    )


class SongList(generic.ListView):
    model = Song
    def get_queryset(self):
        return Song.objects.annotate(
            q_count=count_by_type('q')
        ).annotate(
            q_min=agg_pc(Min, 'q')
        ).annotate(
            q_avg=agg_pc(Avg, 'q')
        ).annotate(
            q_max=agg_pc(Max, 'q')
        ).annotate(
            c_count=count_by_type('c')
        ).annotate(
            c_min=agg_pc(Min, 'c')
        ).annotate(
            c_avg=agg_pc(Avg, 'c')
        ).annotate(
            c_max=agg_pc(Max, 'c')
        )


class SongView(generic.DetailView):
    model = Song
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(SongView, self).get_context_data(**kwargs)
        # get the song
        song = self.object
        # get list of quartet and chorus performances for this person
        context.update({
            'quartet_performances': self.object.songapp_set.filter(
                contestantapp__contest__type='q',
            ).order_by('-contestantapp__contest__date'),
            'chorus_performances':  self.object.songapp_set.filter(
                contestantapp__contest__type='c',
            ).order_by('-contestantapp__contest__date'),
        })
        return context


class PersonList(generic.ListView):
    model = Person
    def get_queryset(self):
        # TODO: Don't show person objects that are just aliases
        return Person.objects.annotate(
            q_count=Sum(Case(
                When(
                    member__contestantapp__contest__type='q',
                    then=1
                ),
                output_field=IntegerField(),
            ))
        ).annotate(
            c_count=Sum(Case(
                When(
                    member__contestantapp__contest__type='c',
                    then=1
                ),
                output_field=IntegerField(),
            ))
        )

class PersonView(generic.DetailView):
    model = Person
    def get_context_data(self, **kwargs):
        # Call the base implementation first to get a context
        context = super(PersonView, self).get_context_data(**kwargs)
        # get the person
        person = self.object
        # get list of quartet and director performances for this person
        context.update({
            'quartet_performances': ContestantApp.objects.filter(
                member__person=person,
                contestant__type='q',
            ).order_by('-contest__date'),
            'director_performances':  ContestantApp.objects.filter(
                member__person=person,
                member__part='director',
            ).order_by('-contest__date'),
        })
        return context


class PersonUpdate(generic.UpdateView):
    model = Person
    form_class = PersonForm


def ContestUpload(request):
    if request.method == 'POST':
        form = UploadFileForm(request.POST, request.FILES)
        if form.is_valid():
            # read json file
            json_data = json.loads(request.FILES['file'].read())
            # check whether we have a single object or a list of objects
            # if we got a single object, put it in a list
            d_list = json_data if isinstance(json_data, list) else [json_data,]
            # iterate over list of objects
            for d in d_list:
                # delay needed to prevent disk I/O error for some reason
                time.sleep(0.5)

                # parse the date fields and calculate missing scores and percentages
                prepare_for_import(d)

                # import it
                import_contest_from_dict(d)

            # Suck Sess
            return HttpResponse('Success!')

    else:
        form = UploadFileForm()
    return render(request, 'scores/contest_upload.html', {'form': form})


def Import(request):
    if 'website_url' in request.POST:
        # display list of PDF files on the given website
        context = {'form': ImportFileListForm(website_url=request.POST['website_url'])}
        return render(request, 'scores/import.html', context)
    elif 'import_urls' in request.POST:
        # import URLS
        urls = request.POST.getlist('import_urls')
        contests = []
        for url in urls:
            try:
                contest = get_contest_dict_from_url(url)
            except AttributeError:  # this probably means that the scoresheet is not of the right format, skip it
                continue
            prepare_for_import(contest)
            import_contest_from_dict(contest)
            contests.append(contest)
        return HttpResponse("############################################################<br />".join((pf(c).replace(' ', '&nbsp;').replace('\n', '<br />') for c in contests)))
    else:
        # display list of websites to get PDF files from
        context = {'form': ImportWebsiteListForm()}
        return render(request, 'scores/import.html', context)


def UpdateAliases(request):
    responses = []
    for m in Member.objects.all():
        while m.person.alias_of:
            responses.append('Changed %s to %s in %s' % (m.person, m.person.alias_of, m.contestantapp.contestant))
            m.person = m.person.alias_of
        m.save()
    return HttpResponse('<p>'.join(responses))

from . import_rtf import txt_to_dicts
from . import_from_dict import import_contest_from_dict

def import_rtf_view(request):

    dir = r'C:\Users\Li-Wen Yip\Documents\GitHub\barbershop-scoresheet-scraper\BABS RTF'

    for contest in txt_to_dicts(dir):
        contest['date'] = datetime.strptime(contest['date'], '%d/%m/%Y')
        contest['url'] = contest.pop('filename')
        import_contest_from_dict(contest)

    return HttpResponse('Import successful')
