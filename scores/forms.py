from bs4 import BeautifulSoup
from urllib.request import urlopen
from urllib.parse import urlparse, urljoin
from django import forms
from .scrape_pdf import *
from .models import *
from dal import autocomplete


class PersonForm(forms.ModelForm):
    alias_of = forms.ModelChoiceField(
        queryset=Person.objects.all(), # TODO: Exclude person objects that are aliases
        widget=autocomplete.ModelSelect2(url='scores:person_autocomplete')
    )

    class Meta:
        model = Person
        fields = ('alias_of',)

    # TODO: Add logic to update the person_id on all relevant objects, and prevent setting setting alias to same person


class UploadFileForm(forms.Form):
    file = forms.FileField()

class ImportWebsiteListForm(forms.Form):
    website_url = forms.ChoiceField(widget=forms.RadioSelect, choices=(
        ('http://www.babsguildofjudges.com/contests/contest-results/', 'BABS Latest Results - http://www.babsguildofjudges.com/contests/contest-results/'),
        ('http://www.babsguildofjudges.com/results-archive/', 'BABS Archive Results - http://www.babsguildofjudges.com/results-archive/'),
        ('https://www.labbs.org.uk/convention/results.shtml', 'LABBS Results - https://www.labbs.org.uk/convention/results.shtml'),
        ('https://www.barbershop.org.au/dbpage.php?pg=results', 'BHA Results - https://www.barbershop.org.au/dbpage.php?pg=results'),
    ))

class ImportFileListForm(forms.Form):
    def __init__(self, *args, **kwargs):
        # extract kwarg and call parent constructor
        url = kwargs.pop('website_url')
        super(ImportFileListForm, self).__init__(*args, **kwargs)

        # get all the pdf links from the given website
        soup = BeautifulSoup(urlopen(url).read(), "lxml")
        a_tags = soup.find_all('a', href=re.compile('\.pdf$'))

        # create the list of choices
        base_url = soup.base['href'] if soup.base else url
        choices = [
            (
                urljoin(base_url, a['href']),
                " - ".join((urlparse(a['href']).path, a.string))
            )
            for a in a_tags]

        # create selector widget
        self.fields['import_urls'] = forms.MultipleChoiceField(
            widget=forms.SelectMultiple(attrs={'size':'20'}),
            choices=choices
        )

