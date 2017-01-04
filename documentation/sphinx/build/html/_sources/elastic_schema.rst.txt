
Elasticsearch data layout
=========================

In order to get the most from all the tools, the recommended specification should be followed when importing data to Elasticsearch.

Example layout
--------------

The following code-block shows how the data looks like in the example "journal" dataset.

.. code-block:: json

    {
        "journal": {
            "texta": {
                "facts": [
                
                ]
            },
            "articles": [
                {
                    "author": "some author",
                    "content": {
                        "text": "some content raw text blob",
                        "lemmas": "some content lemmas"
                    },
                    "date": "some date",
                    "id": "some id",
                    "issue": "some issue",
                    "rubric": "some rubric",
                    "title": "some title"
                }
            ]
        }
    }
    

Details
-------

There are several important aspects when it comes to data.

Facts
+++++

First of all is the "texta" mapping with "facts" in it. **Facts** denote annotations
with which we provide some extra knowledge to the words or phrases. Annotations in TEXTA context are used to represent information extraction
output. Maybe we have built a grammar which describes how to extract monetary values along with units. In this case we can detect the matched
text segments and attach corresponding labels which we can later either browse or enhance our search engine with.

Each fact has the following structure:

.. code-block:: json

    {
        "doc_path": "content.text",
        "doc_type": "articles",
        "doc_id": "15",
        "fact": "money",
        "spans": "[[12, 15]]"
    }

which we can interpret as mapping *doc_type* has document with *ID* 15, the document has a nested feature *content.text*, the feature has a
substring in character position range [12,14] (last index is excluded) and the content of the substring is money-related.

If the corresponding document's *content.text* was "I inherited $10 from my poor grandfather.", it would highlight "*$10*".
    
We don't have any facts in the initial dataset.


Data mapping
++++++++++++

Each index should have an arbitrarily named mapping which contains the actual data. In example data it is called "articles" but it could be
anything as long as it explains the underlying data reasonably well. Ideally index shouldn't contain more than one data mapping.


Feature structure
+++++++++++++++++

Features can either be plain (single values) or in nested format. The most common data type for plain features is string. For example

.. code-block:: json

    {
        "author": "Terry Pratchett"
    }
    
In fact, string is the preferred data type for text blobs, dates and ids.
    
Sometimes we are, however, interested in storing some metadata or "layers" about our feature. In our context it is mostly linguistic data about our 
text blob which allows us to make more elaborate queries and write more detailed grammar definitions.

Suppose that we want to find all documents which talk about "bribing". Due to inflection, we can't come up with (or atleast it's not convenient)
to consider all the possible sufficies or word formations we should potentially keep our eyes out for. What we can do is store a lemmatized
layer along with the raw text.

.. code-block:: json

    {
        "text": "Many dogs jumped over the rainbows .",
        "lemmas": "many dog jump over the rainbow ."
    }
    
Now, whenever we search some of its words in canonical form or "lemma", we can get the original documents that covered the topic.

Another scenario is when we want to make more elaborate grammar definitions that expect part of the match to occur on one layer and part on
another layer of the same feature. For example, we may be interested in documents which are about the game GO. Since a very common verb has
the same spelling, we would like to limit our matches, so that only documents in which GO is a noun are returned. For that reason we need
lemma and part-of-speech layers.

.. code-block:: json

    {
        "text": "Let's play GO .",
        "lemmas": "let's play go .",
        "pos": "V V N Z"
    }
    
Now we can query documents which contain lemma "go" and have noun *N* at the corressponding token index.

.. note::

    In order for interlayer queries to work, the layers must have the same number of tokens.