'use strict';

function currentFilters() {
    const filters = {};
    document.querySelectorAll('#https-table [data-filter]').forEach((input) => {
        const key = input.getAttribute('data-filter');
        filters[key] = input.type === 'checkbox' ? input.checked : input.value.trim().toLowerCase();
    });
    return filters;
}

function rowMatch(row, filters) {
    const d = row.dataset;
    if (filters.version && !(d.version || '').toLowerCase().startsWith(filters.version)) {
        return false;
    }
    const contains = ['tls', 'csp', 'html', 'country', 'network'];
    for (let i = 0; i < contains.length; i += 1) {
        const key = contains[i];
        if (filters[key] && !(d[key] || '').toLowerCase().includes(filters[key])) {
            return false;
        }
    }
    if (filters.ipv6 && d.ipv6 !== '1') {
        return false;
    }
    if (filters.search && d.search !== '1') {
        return false;
    }
    if (filters.google && d.google !== '1') {
        return false;
    }
    if (filters['asn-privacy'] && Number(d.asnPrivacy) < 0) {
        return false;
    }
    return true;
}

function applyFilters() {
    const filters = currentFilters();
    const rows = document.querySelectorAll('#https-table > tbody > tr');
    let visible = 0;
    rows.forEach((row) => {
        const show = rowMatch(row, filters);
        row.hidden = !show;
        if (show) {
            visible += 1;
        }
    });
    const count = document.getElementById('https-count');
    if (count) {
        count.textContent = String(visible);
    }
}

function applyTimes() {
    const select = document.getElementById('time-select');
    const key = select ? select.value : 'all';
    document.querySelectorAll('.timing').forEach((el) => {
        let times = {};
        try {
            times = JSON.parse(el.getAttribute('data-times') || '{}');
        } catch (err) {
            times = {};
        }
        const pair = times[key];
        el.replaceChildren();
        if (!pair) {
            return;
        }
        const span = document.createElement('span');
        span.textContent = pair[0];
        if (pair[1]) {
            span.className = 'value-responsetime';
            span.style.backgroundColor = pair[1];
        }
        el.append(span);
    });
}

document.querySelectorAll('#https-table [data-filter]').forEach((input) => {
    input.addEventListener('input', applyFilters);
    input.addEventListener('change', applyFilters);
});

const timeSelect = document.getElementById('time-select');
if (timeSelect) {
    timeSelect.addEventListener('change', applyTimes);
}
