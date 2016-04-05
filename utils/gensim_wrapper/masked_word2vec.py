import numpy as np
from six import string_types
import gensim

class MaskedWord2Vec(object):

    def __init__(self,word2vec_model):
        self.model = word2vec_model
        self.vocab = word2vec_model.vocab
    
    def most_similar(self, positive=[], negative=[], topn=10, ignored_idxes=[], ignored_dist = -999999):
        """
        Find the top-N most similar words. Positive words contribute positively towards the
        similarity, negative words negatively.
        This method computes cosine similarity between a simple mean of the projection
        weight vectors of the given words, and corresponds to the `word-analogy` and
        `distance` scripts in the original word2vec implementation.
        Example::
          >>> trained_model.most_similar(positive=['woman', 'king'], negative=['man'])
          [('queen', 0.50882536), ...]
        """
        self.model.init_sims()

        if isinstance(positive, string_types) and not negative:
            # allow calls like most_similar('dog'), as a shorthand for most_similar(['dog'])
            positive = [positive]

        # add weights for each word, if not already present; default to 1.0 for positive and -1.0 for negative words
        positive = [(word, 1.0) if isinstance(word, string_types + (np.ndarray,))
                                else word for word in positive]
        negative = [(word, -1.0) if isinstance(word, string_types + (np.ndarray,))
                                 else word for word in negative]

        # compute the weighted average of all words
        all_words, mean = set(), []
        for word, weight in positive + negative:
            if isinstance(word, np.ndarray):
                mean.append(weight * word)
            elif word in self.model.vocab:
                mean.append(weight * self.model.syn0norm[self.model.vocab[word].index])
                all_words.add(self.model.vocab[word].index)
            else:
                raise KeyError("word '%s' not in vocabulary" % word)
        if not mean:
            raise ValueError("cannot compute similarity with no input")
        mean = gensim.matutils.unitvec(np.array(mean).mean(axis=0)).astype(np.float32)
        dists = np.dot(self.model.syn0norm, mean)
        if not topn:
            return dists
        dists[ignored_idxes] = ignored_dist
        best = np.argsort(dists)[::-1][:topn + len(all_words)]
        # ignore (don't return) words from the input
        result = [(self.model.index2word[sim], float(dists[sim])) for sim in best if sim not in all_words]
        return result[:topn]

    def most_similar_cosmul(self, positive=[], negative=[], topn=10, ignored_idxes=[], ignored_dist = -999999):
        """
        Find the top-N most similar words, using the multiplicative combination objective
        proposed by Omer Levy and Yoav Goldberg in [4]_. Positive words still contribute
        positively towards the similarity, negative words negatively, but with less
        susceptibility to one large distance dominating the calculation.

        In the common analogy-solving case, of two positive and one negative examples,
        this method is equivalent to the "3CosMul" objective (equation (4)) of Levy and Goldberg.

        Additional positive or negative examples contribute to the numerator or denominator,
        respectively - a potentially sensible but untested extension of the method. (With
        a single positive example, rankings will be the same as in the default most_similar.)

        Example::

          >>> trained_model.most_similar_cosmul(positive=['baghdad','england'],negative=['london'])
          [(u'iraq', 0.8488819003105164), ...]

        .. [4] Omer Levy and Yoav Goldberg. Linguistic Regularities in Sparse and Explicit Word Representations, 2014.

        """
        self.model.init_sims()

        if isinstance(positive, string_types) and not negative:
            # allow calls like most_similar_cosmul('dog'), as a shorthand for most_similar_cosmul(['dog'])
            positive = [positive]

        all_words = set()

        def word_vec(word):
            if isinstance(word, np.ndarray):
                return word
            elif word in self.model.vocab:
                all_words.add(self.model.vocab[word].index)
                return self.model.syn0norm[self.model.vocab[word].index]
            else:
                raise KeyError("word '%s' not in vocabulary" % word)

        positive = [word_vec(word) for word in positive]
        negative = [word_vec(word) for word in negative]
        if not positive:
            raise ValueError("cannot compute similarity with no input")

        # equation (4) of Levy & Goldberg "Linguistic Regularities...",
        # with distances shifted to [0,1] per footnote (7)
        pos_dists = [((1 + np.dot(self.model.syn0norm, term)) / 2) for term in positive]
        neg_dists = [((1 + np.dot(self.model.syn0norm, term)) / 2) for term in negative]
        dists = np.prod(pos_dists, axis=0) / (np.prod(neg_dists, axis=0) + 0.000001)

        if not topn:
            return dists
        dists[ignored_idxes] = ignored_dist
        best = np.argsort(dists)[::-1][:topn + len(all_words)]
        # ignore (don't return) words from the input
        result = [(self.model.index2word[sim], float(dists[sim])) for sim in best if sim not in all_words]
        return result[:topn]
