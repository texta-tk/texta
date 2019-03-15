class ShowShortVersion extends HTMLElement {
    //declare observed attributes
    static get observedAttributes() {
        return ['open'];
    }

    get open() {
        return this.hasAttribute('open');
    }

    set open(val) {
        // Reflect the value of the open property as an HTML attribute.
        if (val) {
            this.setAttribute('open', '');
        } else {
            this.removeAttribute('open');
        }
    }

    get toggleAllTracker() {
        return this.hasAttribute('toggle-all-tracker');
    }

    set toggleAllTracker(val) {
        // Reflect the value of the open property as an HTML attribute.
        if (val) {
            this.setAttribute('toggle-all-tracker', '');
        } else {
            this.removeAttribute('toggle-all-tracker');
        }
    }

    attributeChangedCallback(name, oldValue, newValue) {
        // callback when the attribute is changed
        if (this.open) {
            this.textElement.innerText = this.getAttribute('data-text')
        } else {
            this.textElement.innerText = this.getAttribute('data-placeholder-string')
        }
    }

    constructor() {
        super();
        // no shadow dom because bootstrap, hundreds of instances per page, no point to make my own dropdown, no static template rendering bonuses because have to change template

        this.setAttribute('role', 'button')
        this.setAttribute('class', 'btn-group dropdown')

        this.textElement = this._createTextElementSkeleton()
        this.textElement.innerText = this.getAttribute('data-placeholder-string')
        this.appendChild(this.textElement)

        let dropdownElement = this._createDropdownSkeleton()

        let dropdownItem1 = this._createDropdownItem('Toggle content')
        dropdownItem1.addEventListener('click', e => {
            this.open = !this.open
        });
        dropdownElement.appendChild(dropdownItem1)

        let dropdownItem2 = this._createDropdownItem('Toggle all')
        dropdownItem2.addEventListener('click', e => {
            // dont hate
            if (!this.toggleAllTracker) {
                ShowShortVersion.expandEachElement(this.getAttribute('data-tracker-id'))
            } else {
                ShowShortVersion.collapseEachElement(this.getAttribute('data-tracker-id'))
            }

        });
        dropdownElement.appendChild(dropdownItem2)

        this.appendChild(dropdownElement)

    }

    static expandEachElement(id) {
        $('show-short-version[data-tracker-id=' + id + ']').each(function () {
            this.open = true;
            this.toggleAllTracker = true
        });
    }

    static collapseEachElement(id) {
        $('show-short-version[data-tracker-id=' + id + ']').each(function () {
            this.open = false;
            this.toggleAllTracker = false
        });
    }

    _createTextElementSkeleton() {
        let textElement = document.createElement('span')
        textElement.setAttribute('data-toggle', 'dropdown')
        textElement.setAttribute('aria-haspopup', 'true')
        textElement.setAttribute('aria-expanded', 'false')
        return textElement
    }

    _createDropdownSkeleton() {
        let dropdownElement = document.createElement('ul')
        dropdownElement.setAttribute('class', 'dropdown-menu ')
        return dropdownElement
    }

    _createDropdownItem(itemText) {
        let dropdownItem = document.createElement('li')
        let dropdownItemContent = document.createElement('a')
        dropdownItemContent.setAttribute('href', '#')
        dropdownItemContent.innerText = itemText

        dropdownItem.appendChild(dropdownItemContent)
        return dropdownItem
    }

}

// Define the new element
customElements.define('show-short-version', ShowShortVersion);