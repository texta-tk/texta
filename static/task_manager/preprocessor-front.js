$(function () {
    $('#lexicon-classifier-cl-slops').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#lexicon-classifier-slops').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#lexicon-classifier-words-required').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_nr_kws').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_rake_phrase_len').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_model_neg_threshold').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })
    $('#scoro_model_pos_threshold').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_lex_neg_threshold').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })
    $('#scoro_lex_pos_threshold').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_signif_min_term_freq').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_signif_max_term_freq').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_signif_sim_doc_count').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_noun_bg_min_term_freq').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_noun_bg_max_term_freq').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_noun_bg_sim_doc_count').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_rake_bg_min_term_freq').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_rake_bg_max_term_freq').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#scoro_rake_bg_sim_doc_count').slider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })
})

function showIfLemmatize () {
    $('.if-lemmatize').toggleClass('hidden')
}

function showIfAddStopword () {
    $('.if-add-stopword').toggleClass('hidden')
}

function showIfSentiment () {
    $('.if-sentiment').toggleClass('hidden')
}

function showIfMethodLexicon () {
    $('.if-lexicon-based').toggleClass('hidden')
}

function showIfMethodModel () {
    $('.if-model-based').toggleClass('hidden')
}

function showIfKeywordExtraction () {
    $('.if-keyword-extraction').toggleClass('hidden')
}

function showBasedOnMethod () {
    showIfMethodLexicon() // lexicon selected by default so just have to toggle classes onchange
    showIfMethodModel()
}

function showIfSentimentLexCustom (value) {
    if (value === 'Custom') {
        $('.if-sentiment-lex-custom').removeClass('hidden')
    } else {
        $('.if-sentiment-lex-custom').addClass('hidden')
    }
}

function showIfRakeSelected () {
    $('.if-rake-wrapper').toggleClass('hidden')
}

function showIfNounSelected () {
    $('.if-nouns-wrapper').toggleClass('hidden')
}

function showIfBgInfoSelected () {
    $('.if-bg-info-wrapper').toggleClass('hidden')
}

function showIfSignificantWordsSelected () {
    $('.if-significant-words-wrapper').toggleClass('hidden')
}

function showNounIfBgInfoSelected () {
    $('.if-noun-bg-info-selected ').toggleClass('hidden')
}

function showLexContent () {
    $('.c-lex-content-wrapper').toggleClass('hidden')
}

function toggleRequiredPercentage (element) {
    let elementValue = $(element).val()
    $('.required-percentage-wrapper').toggleClass('hidden', elementValue == 'OR')
}
