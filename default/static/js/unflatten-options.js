var toucanApp = toucanApp || {};
(function (namespace)
{
    var _optionsCache = {};

    var outputFormatBox = $('input[name="output_format"]').parents('.form-group'),
        filterField = $('select[name="filter_field"]'),
        filterValue = $('input[name="filter_value"]'),
        filterBox = filterField.parents('.form-group'),
        alertBox = $('#unflatten-options-modal .alert.alert-danger'),
        schemaSelector = $('select[name="schema"]'),
        schemaTreeContainer = $('#tree-container'),
        progressBar = $('#unflatten-options .progress'),
        closeButton = $('.close-modal'),
        preserveFieldsContainer = $('#preserve-fields-container'),
        preserveFieldsSearchInput = $('#preserve_fields_search'),
        modal = $('#unflatten-options-modal'),
        filterFieldEmptyText
    ;

    function showSchemaTree() {
        schemaTreeContainer.removeClass('hidden');
        progressBar.addClass('hidden');
        preserveFieldsSearchInput.removeAttr('disabled');
    }

    function hideSchemaTree() {
        schemaTreeContainer.addClass('hidden');
        progressBar.removeClass('hidden');
        preserveFieldsSearchInput.attr('disabled', 'disabled');
    }

    function addError(selector, withHelpBlock) {
        selector.addClass('has-error');
        if (withHelpBlock)
            selector.find('.help-block').removeClass('hidden');
    }

    function removeError(selector, withHelpBlock) {
        selector.removeClass('has-error');
        if (withHelpBlock)
            selector.find('.help-block').addClass('hidden');
    }

    function validateOutputFormat() {
        /* if no options are checked, show error */
        if (outputFormatBox.find('input:checked').length < 1) {
            if (!outputFormatBox.hasClass('has-error')) {
                addError(outputFormatBox, true);
            }
        } else if (outputFormatBox.hasClass('has-error')) {
            removeError(outputFormatBox, true);
        }
    }

    function validateFilters(e) {
        /* validate the filter options (filter-field, filter-value) */
        if (e.type === 'keyup' || e.type === 'change') {
            removeError(filterBox);
            return true;
        }
        if ((filterField.val()
            && !filterValue.val())
            ||
            (!filterField.val()
            && filterValue.val())
        ) {
            addError(filterBox);
            return false;
        } else if (filterBox.hasClass('has-error')) {
            removeError(filterBox);
        }
    }

    function createSchemaOptionsTree(data, key) {
        var ref = $.jstree.reference(schemaTreeContainer);

        if (ref) {
            ref.destroy();
        }
        if (key) {
            _optionsCache[key] = data;
        }
        schemaTreeContainer.html(data);
        schemaTreeContainer.jstree({
            plugins: ['checkbox', 'search'],
            core: {
                expand_selected_onload : false,
                themes: {
                    dots: false
                }
            },
            checkbox: {
                keep_selected_style: false
            }
        });

        setPreserveFields();
        showSchemaTree();
    }

    function loadSchemaOptions(){
        var schemaSelected = schemaSelector.val();

        hideSchemaTree();
        if (!_optionsCache[schemaSelected] ) {
            $.ajax('/to-spreadsheet/get-schema-options', {
                data: {
                    url: schemaSelected
                }
            }).done(function(data){
                createSchemaOptionsTree(data, schemaSelected);
                loadFilterFieldOptions(data);
            });
        } else {
            createSchemaOptionsTree(_optionsCache[schemaSelected]);
            loadFilterFieldOptions(_optionsCache[schemaSelected]);
        }
    }

    function loadFilterFieldOptions(data){
        var ul = $.parseHTML(data.trim())[0];
        var options = $(ul).children().filter(':not(:has(*))').map(function(i, el){
            return $(el).text().trim();
        }).get();
        var htmlOptions = '<option value="">&lt;' + filterFieldEmptyText + '&gt;</option>';
        $.each(options, function(i, el){
            htmlOptions = htmlOptions + '<option value="'+ el + '">' + el + '</option>';
        });
        filterField.html(htmlOptions);
    }

    function setPreserveFields() {
        /* this function copies the checked values from the tree to hidden inputs in the Unflatten Form */
        var selected = $.jstree.reference(schemaTreeContainer).get_top_selected(true);
        preserveFieldsContainer.empty();

        $.each(selected, function (index, el) {
            var val = el.data.path;
            preserveFieldsContainer.append('<input type="hidden" name="preserve_fields" value="' + val + '"/>')
        });
    }

    function searchInTree(value){
        $.jstree.reference(schemaTreeContainer).search(value);
    }

    namespace.showErrorsFromServer = function (errors) {
        var messages = $('<ul></ul>');
        $.each(errors, function(key, value) {
            $('input[name="'+key+'"]').parents('.form-group').addClass('has-error');
            $.each(value, function(i, e){
                messages.append($('<li></li>').html(e));
            });
        });
        alertBox
            .append(messages)
            .removeClass('hidden')
        ;
    };

    namespace.clear = function() {
        alertBox
            .empty()
            .addClass('hidden')
        ;
        preserveFieldsSearchInput.val('');
        $('.form-group').removeClass('has-error');
    };

    namespace.setFilterFieldEmptyText = function(text){
        filterFieldEmptyText = text;
    };

    outputFormatBox.change(validateOutputFormat);
    filterValue.blur(validateFilters);
    filterValue.keyup(validateFilters);
    filterField.change(validateFilters);
    schemaSelector.change(loadSchemaOptions);
    closeButton.click(setPreserveFields);
    preserveFieldsSearchInput.typeWatch({ callback: searchInTree });
    modal.on('hide.bs.modal', validateFilters);

    $(document).ready(loadSchemaOptions);

})(toucanApp.unflattenOptions = toucanApp.unflattenOptions || {});