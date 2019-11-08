/* eslint-disable no-undef */
/* eslint-disable strict */
/* eslint-disable func-names */
/* eslint-disable quote-props */
/* eslint-disable object-shorthand */
/* eslint-disable no-restricted-syntax */

/**
 * FIXME: use Jinja2
 */

'use strict';

const COMMON_ERROR_MESSAGE = {
    'Connection refused': 'Connection refused',
    'Connection timed out': 'Connection timed out',
    'HTTP status code 4': 'HTTP client error',
    'HTTP status code 5': 'HTTP server error',
    '[Errno -2] Name or service not known': 'Unknown host',
    '[Errno -2] Name does not resolve': 'Unknown host',
    'certificate verify failed': 'Certificate verify failed',
    'hostname \'': 'Hostname doesn\'t match certificate',
};

const SORT_CRITERIAS = ['http.status_code', 'error', 'version', 'tls.grade',
    'html.grade', 'http.grade', 'timing.initial', 'url'];

function getValue(obj, key1, key2, f) {
    let value;
    if (key1 == null) {
        value = obj;
    } else {
        value = obj[key1];
    }
    if (value !== undefined && key2 != null) {
        value = value[key2];
    }
    if (value !== undefined && f != null) {
        value = f(value);
    }
    return value;
}

function setDefault(obj, key, value) {
    if (obj[key] == null) {
        // eslint-disable-next-line no-param-reassign
        obj[key] = value;
    }
}

function listUniq(l) {
    return [...new Set(l)];
}

function normalizeSearxVersion(v) {
    if (typeof (v) !== 'string') {
        return [0, 0, 0, 0, ''];
    }
    const vdash = v.split('-');
    const vdot = vdash[0].split('.').map((i) => parseInt(i, 10));
    if (vdash.length === 1) {
        return [vdot[0], vdot[1], vdot[2], 0, ''];
    }
    if (vdash[1] === 'unknow') {
        return [vdot[0], vdot[1], vdot[2], 0, ''];
    }
    return [vdot[0], vdot[1], vdot[2], parseInt(vdash[1], 10), vdash[2]];
}

function normalizeGrade(grade) {
    if (grade === undefined || grade === null) {
        return '';
    }
    if (grade === '?') {
        return -1;
    }
    const result = ('G'.codePointAt(0) - grade.codePointAt(0)) * 3 + 1;
    if (grade.length === 2 && grade.endsWith('+')) {
        return result + 1;
    }
    if (grade.length === 2 && grade.endsWith('-')) {
        return result - 1;
    }
    return result;
}

function compareTool(a, b, key1, key2, f) {
    const va = getValue(a, key1, key2, f);
    const vb = getValue(b, key1, key2, f);
    if (va === '' && vb !== '') {
        return 1;
    }
    if (vb === '' && va !== '') {
        return -1;
    }
    if (va < vb) {
        return 1;
    }
    if (va > vb) {
        return -1;
    }
    return 0;
}

function compareVersion(a, b) {
    const nsva = normalizeSearxVersion(a);
    const nsvb = normalizeSearxVersion(b);
    for (let i = 0; i < 3; i += 1) {
        const result = compareTool(nsva, nsvb, i);
        if (result !== 0) {
            return result;
        }
    }
    return 0;
}

const CompareFunctionCriterias = {
    'http.status_code': (a, b) => -compareTool(a, b, 'http', 'status_code'),
    'error': (a, b) => -compareTool(a, b, 'error'),
    'version': (a, b) => compareVersion(a.version, b.version),
    'tls.grade': (a, b) => compareTool(a, b, 'tls', 'grade', normalizeGrade),
    'html.grade': (a, b) => compareTool(a, b, 'html', 'grade', normalizeGrade),
    'http.grade': (a, b) => compareTool(a, b, 'http', 'grade', normalizeGrade),
    'timing.initial': (a, b) => -compareTool(a, b, 'timing', 'initial'),
    'url': (a, b) => -compareTool(a, b, 'url'),
};

function compareFunctionCompose(...criterias) {
    const criteriaFunctions = criterias.map((criteriaName) => CompareFunctionCriterias[criteriaName]);
    return (a, b) => {
        for (let i = 0; i < criteriaFunctions.length; i += 1) {
            const result = criteriaFunctions[i](a, b);
            if (result !== 0) {
                return result;
            }
        }
        return 0;
    };
}

function translateValue(value, fromMinValue, fromMaxValue, toMinValue, toMaxValue, reverse) {
    const valuei = Math.max(fromMinValue, Math.min(parseFloat(value), fromMaxValue)) - fromMinValue;
    const valuem = Math.round((valuei * (toMaxValue - toMinValue)) / (fromMaxValue - fromMinValue));
    if (reverse) {
        return toMaxValue - valuem;
    }
    return valuem + toMinValue;
}

function hslCss(h, s, l) {
    return `hsl(${h}, ${s}%, ${l}%)`;
}

function hslResponseTime(value, successRate) {
    const responseTimeInPercentage = translateValue(value, 0.1, 2, 0, 100, true);
    const successRateNormalized = translateValue(successRate || 100, 40, 90, 0, 100, false);
    const percentageShown = (responseTimeInPercentage / 100) * (successRateNormalized / 100) * 100;
    const h = translateValue(percentageShown, 0, 100, 0, 128, false);
    const s = translateValue(percentageShown, 0, 100, 39, 54, true);
    const l = 54;
    return hslCss(h, s, l);
}

function hslGrade(grade) {
    const l = 54;
    if (grade === -1) {
        return hslCss(0, 0, l);
    }
    const value = Math.min(17, Math.max(0, normalizeGrade(grade) - 3));
    const h = translateValue(value, 0, 17, 0, 128, false);
    const s = translateValue(value, 0, 17, 39, 54, true);
    return hslCss(h, s, l);
}

function hslGradeHtml(grade) {
    const l = 54;
    if (grade === '?') {
        return hslCss(0, 0, l + 20);
    }
    const value = Math.min(100, Math.max(0, normalizeGrade(grade) - 3));
    const h = translateValue(value, 0, 17, 0, 128, false);
    const s = translateValue(value, 0, 17, 39, 54, true);
    return hslCss(h, s, l);
}

function formatResponseTime(value) {
    return new Intl.NumberFormat('en', { maximumFractionDigits: 3, minimumFractionDigits: 3 }).format(value);
}

function createTooltip(h, e, tooltipContent) {
    if (!tooltipContent) {
        return e;
    }
    if (Array.isArray(tooltipContent) && tooltipContent.length === 0) {
        return e;
    }
    return h('span', [
        e,
        h('span', { staticClass: 'info-tooltip' }, tooltipContent),
    ]);
}

Vue.component('time-component', {
    props: ['value'],
    render: function (h) {
        if (this.value != null) {
            let successRate = 100;
            let value;
            let tooltip;
            if (typeof (this.value) === 'object') {
                value = this.value.all.median;
                if (value === undefined) {
                    value = this.value.all.value;
                }
                successRate = this.value.success_percentage;
                tooltip = [
                    h('p', `${successRate}% success`),
                ];
                const serverTiming = this.value.server;
                if (serverTiming !== undefined) {
                    const serverMedian = serverTiming.median || serverTiming.value;
                    tooltip.push(h('p', `server time: ${formatResponseTime(serverMedian)}`));
                }
            } else {
                value = this.value;
                tooltip = null;
            }
            if (value !== undefined) {
                return createTooltip(h,
                    h('span', {
                        staticClass: 'value-responsetime',
                        attrs: {
                            style: `background-color:${hslResponseTime(value, successRate)}`,
                        },
                    }, formatResponseTime(value)), tooltip);
            }
        }
        return undefined;
    },
});

Vue.component('timestamp-component', {
    props: ['value'],
    template: '<time datetime="{{ new Date(value * 1000).toString() }}">{{ new Date(value * 1000).toString() }}</time>',
});

Vue.component('html-component', {
    props: ['value', 'hashes', 'url'],
    render: function (h) {
        if (this.value != null && this.value !== undefined) {
            // eslint-disable-next-line prefer-const
            let { grade, ressources } = this.value;
            const tooltip = [];
            if (ressources !== undefined && this.hashes != null && this.hashes !== undefined) {
                const r = [];
                const { link: ressourceLink, inline_script: ressourceInlineScripts, error } = ressources;
                if (ressourceLink) {
                    // inline scripts
                    let unknownCountMin = 1000000;
                    let unknownInlineScriptCount = 0;
                    for (const ressourceDetail of ressourceInlineScripts) {
                        const ressourceHash = this.hashes[ressourceDetail.hashRef];
                        if (ressourceHash) {
                            if ('unknown' in ressourceHash) {
                                unknownInlineScriptCount += 1;
                                unknownCountMin = Math.min(unknownCountMin, ressourceHash.count);
                            }
                        }
                    }
                    if (unknownInlineScriptCount > 0) {
                        const attrs = {};
                        const msg = `${unknownInlineScriptCount} unknown inline scripts`;
                        let msg2 = `one is used by ${unknownCountMin} instances`;
                        if (unknownCountMin >= 5) {
                            attrs.style = `background-color:${hslGradeHtml('B')}; color:white`;
                        } else if (unknownCountMin >= 2) {
                            attrs.style = `background-color:${hslGradeHtml('D')}; color:white`;
                        } else {
                            attrs.style = `background-color:${hslGradeHtml('E')}; color:white`;
                            msg2 = 'one only on this instance';
                        }
                        r.push(h('tr', [
                            h('td', { attrs: attrs }, `${msg}, ${msg2}`),
                            h('td', { attrs: attrs }, ''),
                        ]));
                    }
                    // external ressources
                    for (const ressourceType of ['script', 'style', 'link', 'other', 'img']) {
                        if (ressources[ressourceType] !== undefined) {
                            for (const [url, ressourceDetail] of Object.entries(ressources[ressourceType])) {
                                const attrs = {};
                                const ressourceHash = this.hashes[ressourceDetail.hashRef];
                                let extraInfo = null;
                                let addThisRessource = false;
                                if (ressourceDetail.external) {
                                    addThisRessource = true;
                                    attrs.style = `background-color:${hslGradeHtml('F-')}; color:white`;
                                } else if (ressourceDetail.notFetched) {
                                    addThisRessource = true;
                                    attrs.style = `background-color:${hslGradeHtml('?')}; color:white`;
                                    extraInfo = ressourceDetail.error;
                                } else if (ressourceHash) {
                                    extraInfo = ressourceHash.count;
                                    if (ressourceHash.unknown) {
                                        addThisRessource = true;
                                        if (ressourceHash.count >= 5) {
                                            attrs.style = `background-color:${hslGradeHtml('B')}; color:white`;
                                        } else if (ressourceHash.count >= 2) {
                                            attrs.style = `background-color:${hslGradeHtml('D')}; color:white`;
                                        } else {
                                            attrs.style = `background-color:${hslGradeHtml('E')}; color:white`;
                                        }
                                    }
                                }
                                if (addThisRessource) {
                                    r.push(h('tr', [
                                        h('td', { attrs: attrs }, new URL(url, this.url).href),
                                        h('td', { attrs: attrs }, extraInfo),
                                    ]));
                                }
                            }
                        }
                    }
                    if (r.length > 0) {
                        tooltip.push(h('table', r));
                    }
                }
                if (error !== undefined) {
                    tooltip.push(h('p', error));
                }
            }
            if (grade === null || grade === undefined) {
                grade = '?';
            }
            return createTooltip(h, h('span', {
                class: 'value-html',
                attrs: {
                    style: `background-color:${hslGradeHtml(grade)}`,
                },
            }, grade),
            tooltip);
        }
        return undefined;
    },
});

Vue.component('tls-component', {
    props: ['value'],
    render: function (h) {
        if (this.value != null && this.value !== undefined) {
            const { grade, gradeUrl, version } = this.value;
            if (grade != null) {
                return createTooltip(h,
                    h('a', {
                        class: 'value-tls',
                        attrs: {
                            href: gradeUrl,
                            style: `background-color:${hslGrade(grade)}`,
                        },
                    }, grade),
                    [version]);
            }
        }
        return undefined;
    },
});

Vue.component('csp-component', {
    props: ['value'],
    render: function (h) {
        if (this.value != null && this.value !== undefined) {
            const { grade, gradeUrl, version } = this.value;
            if (grade != null) {
                return h('a', {
                    class: 'value-tls',
                    attrs: {
                        href: gradeUrl,
                        title: version,
                        style: `background-color:${hslGrade(grade)}`,
                    },
                }, grade);
            }
        }
        return undefined;
    },
});

Vue.component('certificate-component', {
    props: ['value', 'url'],
    render: function (h) {
        if (this.value != null) {
            const { certificate } = this.value;
            if (certificate.issuer != null) {
                const { hostname } = new URL(this.url);
                return createTooltip(h,
                    h('a', { attrs: { href: `https://crt.sh/?q=${hostname}` } },
                        [
                            certificate.issuer.organizationName,
                            ' (',
                            certificate.issuer.countryName,
                            ')',
                        ]), [
                        h('p', certificate.issuer.commonName),
                        h('p', `From: ${certificate.notBefore}`),
                        h('p', `To: ${certificate.notAfter}`),
                        h('p', `Serial number: ${certificate.serialNumber}`),
                        h('p', `SHA256: ${certificate.sha256}`),
                    ]);
            }
        }
        return undefined;
    },
});

Vue.component('network-component', {
    props: ['value', 'field'],
    render: function (h) {
        if (this.value != null) {
            if (this.value != null && Object.keys(this.value).length > 0) {
                // element body
                const networks = Object.keys(this.value).map((ip) => {
                    if (this.value[ip].whois != null) {
                        return this.value[ip].whois[this.field];
                    }
                    return null;
                });
                const networksList = listUniq(networks).join(', ');
                // tooltip
                const reverseIpHosts = listUniq(Object.keys(this.value).map((ip) => this.value[ip].reverse || ip));
                const reverseIpHostElements = reverseIpHosts.map((host) => h('p', host));
                return createTooltip(h, h('span', networksList), [reverseIpHostElements]);
            }
        }
        return undefined;
    },
});

function applyStrFilter(r, filterValue, f) {
    if (typeof filterValue === 'undefined' || filterValue === null) {
        return r;
    }
    const filterValueStriped = filterValue.trim().toLowerCase();
    if (filterValueStriped === '') {
        return r;
    }
    return r.filter((detail) => f(filterValueStriped, detail));
}

function filterIndexOf(filterValue, value) {
    return (value || '').toLowerCase().indexOf(filterValue) >= 0;
}

function filterStartsWith(filterValue, value) {
    return (value || '').toLowerCase().startsWith(filterValue);
}

function getErrorKey(errorMessage) {
    if (typeof errorMessage === 'string') {
        for (const [errorKey, errorTitle] of Object.entries(COMMON_ERROR_MESSAGE)) {
            if (errorMessage.startsWith(errorKey)) {
                return errorTitle;
            }
        }
    }
    return 'Others';
}

// eslint-disable-next-line no-new
new Vue({
    el: '#searxinstances',
    data: () => ({
        filters: {
            version: '',
            html_grade: '',
            csp_grade: '',
            tls_grade: '',
            network_x_whois_1: '',
            network_x_whois_2: '',
            google: false,
        },
        selected_tab: 'online',
        timestamp: undefined,
        instances: [],
        instances_nosearx: [],
        instances_ko: [],
        instances_per_ips: {},
        hashes: [],
        engines: {},
    }),
    computed: {
        instances_filtered: function () {
            let result = this.instances;
            result = applyStrFilter(result, this.filters.version, (f, detail) => filterStartsWith(f, detail.version));
            result = applyStrFilter(result, this.filters.csp_grade, (f, detail) => filterIndexOf(f, detail.http.grade));
            result = applyStrFilter(result, this.filters.tls_grade, (f, detail) => filterIndexOf(f, detail.tls.grade));
            result = applyStrFilter(result, this.filters.html_grade,
                (f, detail) => filterIndexOf(f, detail.html.grade));
            result = applyStrFilter(result, this.filters.network_x_whois_1,
                (f, detail) => {
                    for (const ipInfo of Object.values(detail.network)) {
                        return (ipInfo.whois[1] || '').toLowerCase().indexOf(f) >= 0;
                    }
                    return false;
                });
            result = applyStrFilter(result, this.filters.network_x_whois_2,
                (f, detail) => {
                    for (const ipInfo of Object.values(detail.network)) {
                        return ipInfo.whois[2].toLowerCase().indexOf(f) >= 0;
                    }
                    return false;
                });
            if (this.filters.google) {
                result = result.filter((detail) => detail.timing.search_go.success_percentage > 0);
            }
            // sort
            const compareInstance = compareFunctionCompose(...SORT_CRITERIAS);
            result.sort(compareInstance);
            return result;
        },
    },
    created: function () {
        // eslint-disable-next-line arrow-body-style
        fetch('data/instances.json').then((response) => {
            return response.json().then((json) => {
                const rawInstances = json.instances;
                this.timestamp = json.timestamp;
                const instances = [];
                const instancesWithError = {};
                const instancesWithoutSearx = [];
                let instancesPerIps = {};
                for (const [url, instance] of Object.entries(rawInstances)) {
                    instance.url = url;

                    // easier templates
                    setDefault(instance, 'network', {});
                    setDefault(instance, 'tls', {});
                    setDefault(instance.tls, 'certificate', {});
                    setDefault(instance, 'timing', {});
                    setDefault(instance.timing, 'index', {});
                    setDefault(instance.timing.index, 'all', {});
                    setDefault(instance.timing, 'search_wp', {});
                    setDefault(instance.timing.search_wp, 'all', {});
                    setDefault(instance.timing, 'search_go', {});
                    setDefault(instance.timing.search_go, 'all', {});
                    setDefault(instance, 'html', {});
                    setDefault(instance.html, 'grade', '');

                    // engines
                    if (instance.status) {
                        for (const engine of instance.status) {
                            this.engines[engine] = true;
                        }
                    }

                    // dispatch instance
                    if (instance.error === undefined) {
                        if (instance.version !== null) {
                            instances.push(instance);
                        } else {
                            instancesWithoutSearx.push(instance);
                        }
                    } else {
                        const errorKey = getErrorKey(instance.error);
                        setDefault(instancesWithError, errorKey, []);
                        instancesWithError[errorKey].push(instance);
                    }

                    // find instances sharing the same ip set
                    // eslint-disable-next-line no-restricted-syntax
                    for (const ip of Object.keys(instance.network)) {
                        if (ip !== 'error') {
                            setDefault(instancesPerIps, ip, []);
                            instancesPerIps[ip].push(instance.url);
                        }
                    }
                }

                // find instances sharing the same ip set
                instancesPerIps = Object.keys(instancesPerIps)
                    .filter((ip) => instancesPerIps[ip].length > 1)
                    .reduce((obj, key) => {
                        instancesPerIps[key].sort();
                        const value = instancesPerIps[key].join('|');
                        setDefault(obj, value, []);
                        // switch key and value: urls.join('|') as key, ips as value
                        obj[value].push(key);
                        return obj;
                    }, {});

                const compareInstance = compareFunctionCompose(...SORT_CRITERIAS);
                instancesWithoutSearx.sort(compareInstance);
                for (const instanceList of Object.values(instancesWithError)) {
                    instanceList.sort(compareInstance);
                }
                this.instances = instances;
                this.instances_ko = instancesWithError;
                this.instances_nosearx = instancesWithoutSearx;
                this.instances_per_ips = instancesPerIps;
                this.hashes = json.hashes;
            });
        });
    },
});
