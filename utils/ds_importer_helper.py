import requests


def check_for_analyzer(display_name: str, analyzer_name: str, es_url):
    response = requests.get(url="{}/_analyze".format(es_url), json={
        "analyzer": analyzer_name,
        "text": ["this is a test", "the second text"]
    })

    if response.status_code == 200:
        return {"display_name": display_name, "analyzer": analyzer_name}

    elif response.status_code == 400:
        return None
