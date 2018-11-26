/* global LINK_TASK_MANAGER */
var PREFIX = LINK_TASK_MANAGER

$(function () {
    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
        $('.data-table:visible').each(function (e) {
            $($.fn.dataTable.tables(true)).DataTable().columns.adjust().responsive.recalc()
        })
        localStorage.setItem('lastTab', $(this).attr('href'))
    })
    /* inits all datatables */
    $('.data-table').DataTable({
        'paging': false,
        'ordering': false,
        'info': false,
        'searching': false,
        responsive: {
            details: true
        }
    })
    /* dont show non datatables version */
    $('.tasks-table').toggleClass('hidden')

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

    // go to the latest tab, if it exists:
    let lastTab = localStorage.getItem('lastTab')

    if (lastTab) {
        $('[href="' + lastTab + '"]').tab('show')
    } else {
        console.log('here')
        let element = $('.flex-row.nav.nav-tabs li').first()
        element.addClass('active')
        /* TODO no redirect if not first time visit */
        /* console.log($(element.children()[0])[0].val()) */
    }
})

function start_task (task_id) {
    let formElement = document.getElementById('task_params')
    $('<input>').attr('type', 'hidden').attr('name', 'task_type').val(task_id).appendTo(formElement)

    var request = new XMLHttpRequest()
    request.onreadystatechange = function () {
        location.reload()
    }

    request.open('POST', PREFIX + '/start_task')
    request.send(new FormData(formElement), true)
}

function select_preprocessor (task_id) {
    let preprocessor_key = $('#' + task_id + '_preprocessor_key').val()
    $('[id^=params-]').addClass('hidden')
    $('#params-' + preprocessor_key).removeClass('hidden')
}

function delete_task (task_id) {
    let data = {
        task_id: task_id
    }

    swal({
        title: 'Are you sure?',
        text: 'This will remove the task and it\'s resources.',
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete!'

    }).then((result) => {
        if (result.value) {
            $.post(PREFIX + '/delete_task', data, function (data) {
                location.reload()
            })
        }
    })
}

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
