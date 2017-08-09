del .\db.sqlite3
python .\manage.py makemigrations scores
python .\manage.py migrate
python .\manage.py runserver