
function toggleFullscreen () {
    $('#grid-wrapper-searcher-id').toggleClass('grid-wrapper-searcher')
    $('#grid-wrapper-searcher-id').toggleClass('grid-1-col-default')
    $('.grid-wrapper-sidebar').toggleClass('hidden')
    /* if searcher is displayed, a different fullscreen button is used */
    if ($('.dataTables_scrollBody').length !== 0) {
        $('.glyphicon-fullscreen-content-searcher.new-toggle').toggleClass('hidden')
    } else {
        $('.glyphicon-fullscreen-content').toggleClass('hidden')
    }
    /* global recalcDatatablesHeight */
    /* global examplesTable */
    if (examplesTable) {
        examplesTable.columns.adjust()
        recalcDatatablesHeight()
    }
}
function exportData (exportType) {
    var queryArgs = $('#filters').serializeArray()

    queryArgs.push({
        name: 'export_type',
        value: exportType
    })

    if (exportType === 'agg') {
        queryArgs.push({
            name: 'filename',
            value: $('#export-file-name-agg').val() + '.csv'
        })
    } else {
        queryArgs.push({
            name: 'filename',
            value: $('#export-file-name-example').val() + '.csv'
        })
        var extentDec = $('input[name=export-extent]:checked').val()
        /* global examplesTable */
        var pagingInfo = examplesTable.page.info()

        switch (extentDec) {
        case 'page':
            queryArgs.push({
                name: 'examples_start',
                value: pagingInfo.start
            })
            queryArgs.push({
                name: 'num_examples',
                value: pagingInfo.length
            })
            break
        case 'pages':
            var startPage = Number($('#export-start-page').val()) - 1
            var endPage = Number($('#export-end-page').val()) - 1
            queryArgs.push({
                name: 'examples_start',
                value: startPage * pagingInfo.length
            })
            queryArgs.push({
                name: 'num_examples',
                value: (endPage - startPage + 1) * pagingInfo.length
            })

            break
        case 'all':
            queryArgs.push({
                name: 'num_examples',
                value: '*'
            })
            break
        case 'rows':
            queryArgs.push({
                name: 'examples_start',
                value: 0
            })
            queryArgs.push({
                name: 'num_examples',
                value: Number($('#export-rows').val())
            })
            break
        }

        var featuresDec = $('input[name=export-features]:checked').val()
        var features = []
        if (featuresDec === 'all') {
            var options = $('#toggle-column-select option')
            features = $.map(options, function (option) {
                return option.text
            })
        } else {
            $('#toggle-column-select option').each(function () {
                if (this.selected) {
                    features.push($(this).text())
                }
            })
        }
        /*
        $('.buttons-columnVisibility').each(function () {
            if (!$(this).hasClass('toggleAllButton')) {
                if (features_dec == 'all') {
                    features.push($(this).text())
                } else if ($(this).hasClass('active')) {
                    features.push($(this).text())
                }
            }
        }) */

        queryArgs.push({
            name: 'features',
            value: features
        })
    }

    /* global PREFIX */

    $.ajax({
        url: PREFIX + '/export_args',
        data: {'args': JSON.stringify(queryArgs)},
        type: 'POST',
        success: function (result) {
            /*really hacky, but no other ideas how to do this, post args and then set session variable nad then open get*/
            window.open(PREFIX + '/export')
        }
    })
    /*    var query = PREFIX + '/export?args=' + JSON.stringify(queryArgs)
      window.open(query)*/
}
function removeByQuery () {
    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()

    request.onreadystatechange = function () {
        if (request.readyState === 4 && request.status === 200) {
            if (request.responseText.length > 0) {
                /* global swal */
                swal({
                    title: 'The documents are being deleted. Check the progress by searching again.',
                    animation: true,
                    customClass: 'animated fadeInDown',
                    width: 400,
                    padding: 10,
                    position: 'top',
                    type: 'success',
                    timer: 3500,
                    background: '#f9f9f9',
                    backdrop: `
                    rgba(0,0,0,0.0)
                    no-repeat
                    `
                })
            }
        }
    }

    request.open('POST', PREFIX + '/remove_by_query')
    request.send(new FormData(formElement), true)
}
