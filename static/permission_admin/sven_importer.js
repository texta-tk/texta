
$("#new-project-files").change(function() {
    var fileInput = document.getElementById('new-project-files');
    var fileNames = [];
    for (var i = 0; i < fileInput.files.length; ++i) {
        fileNames.push(fileInput.files.item(i).name);
    }

    setOptions(fileNames);
})

function setOptions(optionNames) {
    var select = document.getElementById('new-project-entrance');

    select.innerHTML = "";

    for (var i = 0; i < optionNames.length; i++){
        var option = document.createElement('option');
        option.value = optionNames[i];
        option.innerHTML = optionNames[i];
        select.appendChild(option);
    }

}
