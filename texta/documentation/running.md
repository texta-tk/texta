To run TEXTA in a dev environment you need a tunnel to the elastic search server that hosts the data.

```
ssh -L 9200:localhost:9200 <stacc_username>@p12.stacc.ee
```

```bash
python2.7 manage.py syncdb
python manage.py runserver
```
