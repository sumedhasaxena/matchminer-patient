/**
 * Dynamic OncoTree diagnosis cascade.
 * Renders Level 1..N dropdowns based on available children for the selected branch.
 */
const DiagnosisCascade = (function () {
    let container = null;
    let level1Options = [];
    let onChangeCallback = null;

    function getSelectedPath() {
        if (!container) {
            return [];
        }
        const path = [];
        const selects = container.querySelectorAll('select[data-cascade-level]');
        for (const select of selects) {
            if (!select.value) {
                break;
            }
            path.push(select.value);
        }
        return path;
    }

    function updateHiddenFields() {
        const path = getSelectedPath();
        const primaryEl = document.getElementById('primary_diagnosis');
        const pathEl = document.getElementById('diagnosis_path');
        if (primaryEl) {
            primaryEl.value = path.length ? path[path.length - 1] : '';
        }
        if (pathEl) {
            pathEl.value = JSON.stringify(path);
        }
    }

    async function fetchChildren(term) {
        const response = await fetch(`/get_oncotree_children/${encodeURIComponent(term)}`);
        if (!response.ok) {
            throw new Error(`Failed to load children for ${term}`);
        }
        return response.json();
    }

    function clearFromLevel(levelIndex) {
        if (!container) {
            return;
        }
        container.querySelectorAll('tr[data-cascade-row]').forEach((row) => {
            const level = parseInt(row.dataset.cascadeRow, 10);
            if (level > levelIndex) {
                row.remove();
            }
        });
    }

    function createRow(levelNum, options, selectedValue, isRequired) {
        const tr = document.createElement('tr');
        tr.dataset.cascadeRow = String(levelNum);

        const labelCell = document.createElement('td');
        const label = document.createElement('label');
        label.htmlFor = `diagnosis_level${levelNum}`;
        if (isRequired) {
            const required = document.createElement('span');
            required.className = 'required';
            required.textContent = '*';
            label.appendChild(required);
        }
        label.appendChild(document.createTextNode(`Diagnosis Level ${levelNum}:`));
        labelCell.appendChild(label);

        const selectCell = document.createElement('td');
        selectCell.colSpan = 2;
        const select = document.createElement('select');
        select.id = `diagnosis_level${levelNum}`;
        select.name = `diagnosis_level${levelNum}`;
        select.dataset.cascadeLevel = String(levelNum);
        if (isRequired) {
            select.required = true;
        }

        const placeholder = document.createElement('option');
        placeholder.value = '';
        placeholder.textContent = levelNum === 1
            ? 'Select Level 1'
            : (levelNum === 2 ? 'Select Level 2' : `Select Level ${levelNum} (Optional)`);
        select.appendChild(placeholder);

        options.forEach((optionValue) => {
            const option = document.createElement('option');
            option.value = optionValue;
            option.textContent = optionValue;
            if (selectedValue && optionValue === selectedValue) {
                option.selected = true;
            }
            select.appendChild(option);
        });

        select.addEventListener('change', function () {
            onLevelChange(levelNum);
        });

        selectCell.appendChild(select);
        tr.appendChild(labelCell);
        tr.appendChild(selectCell);
        container.appendChild(tr);
        return select;
    }

    async function onLevelChange(levelNum) {
        clearFromLevel(levelNum);
        updateHiddenFields();
        if (typeof onChangeCallback === 'function') {
            onChangeCallback(getSelectedPath());
        }

        const select = document.getElementById(`diagnosis_level${levelNum}`);
        if (!select || !select.value) {
            return;
        }

        try {
            const children = await fetchChildren(select.value);
            if (children && children.length > 0) {
                createRow(levelNum + 1, children, '', false);
            }
        } catch (error) {
            console.error('Error loading OncoTree children:', error);
        }
    }

    async function init(containerId, level1List, initialPath, options) {
        container = document.getElementById(containerId);
        if (!container) {
            console.error(`Diagnosis cascade container not found: ${containerId}`);
            return;
        }

        level1Options = Array.isArray(level1List) ? level1List.slice() : [];
        onChangeCallback = options && options.onChange ? options.onChange : null;
        const requireLevel1 = !(options && options.requireLevel1 === false);

        container.innerHTML = '';
        const path = Array.isArray(initialPath) ? initialPath.filter(Boolean) : [];

        createRow(1, level1Options, path[0] || '', requireLevel1);

        let parent = path[0] || '';
        let level = 1;
        while (parent) {
            let children = [];
            try {
                children = await fetchChildren(parent);
            } catch (error) {
                console.error('Error loading OncoTree children:', error);
                break;
            }
            if (!children || children.length === 0) {
                break;
            }

            level += 1;
            const selected = path[level - 1] || '';
            createRow(level, children, selected, false);
            parent = selected;
            if (!selected) {
                break;
            }
        }

        updateHiddenFields();
        if (typeof onChangeCallback === 'function') {
            onChangeCallback(getSelectedPath());
        }
    }

    async function reset() {
        await init(container ? container.id : 'diagnosis-cascade', level1Options, [], {
            onChange: onChangeCallback,
            requireLevel1: false
        });
    }

    return {
        init: init,
        reset: reset,
        getSelectedPath: getSelectedPath,
        updateHiddenFields: updateHiddenFields
    };
})();
