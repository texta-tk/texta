.. _api:

API
===

TEXTA API can be used to query or process data without the need to interact with the graphical user interface.

It can be accessed from the address *<texta_address>/api*

Search
------

Searching functionality allows to query documents based on the defined constraints and projections. Documents are queried and returned in JSON format.

.. topic:: Example scenario
    
    Let's presume we have stored a variety of news articles with the following features: title, content, publish date, and author.
    
    We can use TEXTA API to find all the articles by some fixed authors, articles which contain specific keywords or phrases, or articles which are published between two dates by selected authors and of which content contains keywords "president" and "speech", and not keywords "poverty", "unhappiness", and "falling behind".

To download all the documents from the dataset with ID 4, it suffices to call

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/search' -d '{
        "dataset": 4
    }'

Retrieving all the documents isn't necessarily the smartest thing to do. Next we might want to limit the number of documents we receive to 100 and get only the titles and the authors.

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/search' -d '{
        "dataset": 4,
        "fields": ["title", "author"],
        "parameters": {"limit": 100}
    }'

Although we now have some control over how we receive our data, we can't still control what we receive. For that, we have to define constraints which the returned documents must satisfy. Let's retrieve the title and the content of 15 articles published in 2017 by the renowned author John Doe.

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/search' -d '{
        "dataset": 4,
        "fields": ["title", "content"],
        "parameters": {"limit": 15},
        "constraints": [
            {"field":"author","operator":"must","type":"match_phrase","slop":0,"strings":["John Doe"], "class":"string"},
            {"field":"published", "class":"date", "start":"2017-01-01", "end":"2017-12-31"}
        ]
    }'
    
The approach so far is streaming all the matching documents, meaning that the user will receive the data over a period of time with a single request. The returned documents have the following format:

.. code-block:: python

    {"title": "John Doe is the best", "content": "True story."}
    {"title": "John Doe strikes again!", "content": "<Image of a man assaulting tanks with a flower>"}
    {"title": "Johnny hit by a 50 ton tank", "content": "Local hero John Doe stormed a tank on a military parade, but couldn't stop in time."}
    ...

Although streaming is great for downloading huge files, it can be inconvenient to download and process programmatically, which is why TEXTA API also allows to download one batch at a time using the scroll mechanism.

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/search' -d '{
        "dataset": 4,
        "fields": ["title", "content"],
        "parameters": {"size": 20},
        "constraints": [
            {"field":"author","operator":"must","type":"match_phrase","slop":0,"strings":["John Doe"], "class":"string"},
            {"field":"published", "class":"date", "start":"2017-01-01", "end":"2017-12-31"}
        ],
        "scroll": true
    }'

Here we set the "scroll" flag to *True* and defined batch size in the parameters. Batch size defines how many documents will be returned in a single query. The result of the query looks like this:

.. code-block:: python

    {
        "scroll_id": "some very long hash string",
        "total": 1572,
        "hits": [
            {"title": "John Doe is the best", "content": "True story."},
            {"title": "John Doe strikes again!", "content": "<Image of a man assaulting tanks with a flower>"},
            {"title": "Johnny hit by a 50 ton tank", "content": "Local hero John Doe stormed a tank on a military parade, but couldn't stop in time."},
            ... x 17
        ]
    }

Now, when we want to get the next batch of documents, it suffices to query

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/search' -d '{
        "dataset": 4,
        "scroll_id": "that very long hash string we retrieved before"
    }'
    
When all 1572 documents have been retrieved with the batches, the results look like this:

.. code-block:: python

    {
        "scroll_id": "some very long hash string",
        "total": 1572,
        "hits": []
    }

Constraints
^^^^^^^^^^^

Constraints are distinguished by classes.

Textual
"""""""

Textual constraint's class is **string**.

.. code-block:: python

    {"field":"author","operator":"must","type":"match_phrase","slop":0,"strings":["John Doe"], "class":"string"}

**field:** name of the field/feature on which the constraint is applied.

**strings:** keywords or phrases to search for.

**operator:** relationship between the keyword.

    **"must"** - *default* - conjunctive (AND) directive, all the listed keywords must exist in the document.
    
    **"should"** - disjunctive (OR) directive, at least one keyword must exist in the document.
    
    **"must_not"** - prohibitive (NOT) directive, none of the listed keywords can exist in the document.

**type:** defines how the keywords must match.

    **"match"** - at least on token of whitespace split keywords must match, often used for single token keywords, like "John".
    
    **"match_phrase"** - *default* - all the tokens of the keywords must match, can have "slop" number of non-matching words in-between, matches also single tokens.
    
    **"match_phrase_prefix"** - listed keywords must be the preficies of the words actually in the document. Good for matching "look" -> "looking"

**slop:** defines how many other tokens/words can be between any phrase components. Slop 0 wouldn't match "John Doe" to "John Edward Doe", slop 1 would.

Temporal
""""""""

Temporal constraint's class is **date**.

.. code-block:: python

    {"field":"published", "class":"date", "start":"2017-01-01", "end":"2017-12-31"}

**start:** start date.

**end:** end date.

Simple annotational
"""""""""""""""""""

Annotation data is on top of regular features and gives semantical meaning to parts of the feature (words, phrases, sentences, paragraphs). For example, if in our dataset we have articles about annual presidential speeches, we might want to annotate occurrences of "Vladimir Putin", "Donald Trump" or "Barack Obama" with the keyword "president", so that we could later on query the documents, which talk about presidents or presidential speeches, rather than individually list all the presidents that have ever been or will be in the query. Annotation is done via information extraction - either using TEXTA Grammar Miner or external tools.

Simple annotation's constraint class is **fact**. The following constraint finds all the documents, for which there are phrases labelled as "president" AND (beacause of must operator) "prime_minister", meaning that it finds all articles which mention both heads of a state.

.. code-block:: python

    {"field":"content","operator":"must","strings":["president", "prime_minister"], "class":"fact"}

Advanced annotational
"""""""""""""""""""""

"Advanced" annotation queries include the value of the annotation. If simple annotation was only concerned about the fact, whether an article contained a reference to an arbitrary president or prime minister, then advanced annotation allows to query articles, which are about specific presidents. For example about president Donald Trump. The value also helps to differentiate between articles in which Donald Trump was in his presidential role, and articles, in which he wasn't.

Advanced annotation's constraint class is **fact_val**. The following constraint finds all the documents, in which Trump isn't meddling with Russian interests.

.. code-block:: python

    {
        "field":"content",
        "operator":"must",
        "type":"str",
        "constraints":[
               {"name":"president","operator":"=","value":"Donald Trump"},
               {"name":"country","operator":"!=","value":"Russian Federation"}
        ],
        "class":"fact_val"
    }

**type:** type of the fact value.

    **"str"** - textual fact values.
    
    **"num"** - numerical fact values (numbers, dates, etc).

**constraints:** list of fact value constraints, which must match a document, in order for it to be returned.

    Fact value constraints have always **"name"**, **"operator"**, and **"value"** attributes.
    
    "Operator" and "value" attribute values depend on "type" value.
    
    If "type" is "str":
        "operator" can obtain values "=" and "!=";
        "value" is string and in quotes.
        
    If "type" is "num":
        "operator" can obtain values "=", "!=", ">", ">=", "<", "<=";
        "value" is numeric for numbers, string in correct date format for dates.
        

Aggregate
---------

Aggregation allows to calculate document distributions by grouping over specific feature values.


.. topic:: Example scenario
    
    Let's presume we have stored a variety of news articles with the following features: title, content, publish date, and author.
    
    With aggregation we can find out, how many articles were written each month, by aggregating over publish date with monthly interval. We can also find the top publishing authors each year or the most relevant keywords from articles mentioning prime minister candidate during an election period.

If we are interested in finding out, how many articles has each author writtern, we can query it as follows:

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/aggregate' -d '{
        "searches": [{"dataset": 4}],
        "aggregation": [{"field": "author", "type": "string", "sort_by": "terms"}]
    }'

As we can see, aggregation query depends on two attributes - "searches" and "aggregation". "Searches" is a list of search definitions which we have already met in the previous section. Search defines the subset of the original data on which we run the aggregation. This time it's used internally: we are not receiving and documents. 

The possiblity to aggregate against several data subsets allows us to find interesting comparable statistics. For example, we can get the most eager authors on cars and dogs with the following query:

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/aggregate' -d '{
        "searches": [
            {
                "dataset": 4,
                "constraints": [{"field":"content","operator":"must","type":"match_phrase","slop":0,"strings":["car"], "class":"string"}]
            },
            {
                "dataset": 4,
                "constraints": [{"field":"content","operator":"must","type":"match_phrase","slop":0,"strings":["dog"], "class":"string"}]
            },
        ],
        "aggregation": [{"field": "author", "type": "string", "sort_by": "terms"}]
    }'

This returns us a list of two dictionaries - the first dictionary contains aggregation results for the first search, the second dictionary contains results for the second.

So far we have aggregated only over one level - author. However, imagine if we could aggregate over several. For example, what if we want to see the most active author on a monthly basis, without the necessity to explicitly create separate monthly date range searches for several years. Or what if we want to find the favourite words for different authors?

TEXTA API aggregation allows to aggregate over several levels.

To find out the most active authors on a monthly basis, we can execute the following query:

.. code-block:: bash

    $ curl -XPOST 'http://localhost:8000/api/aggregate' -d '{
        "searches": [{"dataset": 4}],
        "aggregation": [
            {"field":"published","type":"daterange","start":"2010-02-02","end":"2017-09-01","frequency":"raw_frequency","interval":"month"}
            {"field": "author", "type": "string", "sort_by": "terms"}
        ]
    }'

This returns us the number of documents written by specific authors per each month in the date range.

Aggregation types
^^^^^^^^^^^^^^^^^

Textual
"""""""

The most common aggregation is over the existing text body and its type is "string".

{"field": "content", "type": "string", "sort_by": "significant_terms"}

**sort_by:** defines, how the results will be scored and ordered.

    **"term"** - order by raw document count. If "car" is in more documents than "dog", then "car" takes precedence over "dog".

    **"significant_term"** - order by the level of interest. Term is more interesting if it is more common in the observed data subset than in all the documents.

Temporal
""""""""

Temporal aggregation has type "daterange".

{"field":"published","type":"daterange","start":"2010-02-02","end":"2017-09-01",
"frequency":"raw_frequency","interval":"year"}

**frequency:**

**interval:** length of the time periods into which the time from "start" to "end" is divided.

    **"day"**, **"week"**, **"month"**, **"quarter"**, **"year"**

Simple annotational
"""""""""""""""""""

Simple annotation aggregation has type "fact".

.. code-block:: python

    {"field": "content", "type": "fact", "sort_by": "terms"}

Advanced annotational
"""""""""""""""""""""

Advanced annotation aggregation has a type, which depends on the data type of the values.

If we are interested in textual annotations, we use the type "fact_str".

.. code-block:: python

    {"field": "content", "type": "fact_str", "sort_by": "terms"}

If we are interested in numeric/temporal annotations, we use the type "fact_num".

.. code-block:: python

    {"field": "content", "type": "fact_num", "sort_by": "terms"}


List datasets
-------------

Listing datasets is important in order to construct queries on correct datasets.

To get the list of available and permitted datasets, we issue the following command:

.. code-block:: bash

    curl http://localhost:8000/search_api/list/datasets

which returns

.. code-block:: python

    {"index": "journalA", "id": 2, "mappping": "articles", "author": "superadmin"}
    {"index": "journalB", "id": 3, "mappping": "ancient_articles", "author": "superadmin"}
    {"index": "joy_of_life", "id": 4, "mappping": "stories", "author": "mystery_admin"}

**id:** ID of the dataset, used in TEXTA API searches.

**index:** database name.

**mapping:** table name.

**author:** username of the admin, who added the dataset.

Get dataset field details
-------------------------

It is necessary to know the existing fields and their data types to construct accurate queries.

One can get detailed structure of the dataset with ID 4 with the following query:

.. code-block:: bash

    curl http://localhost:8000/search_api/list/4
    
The response is however rather complicated and often it makes more sense to use TEXTA graphical user interface's Searcher tool to explore the dataset.