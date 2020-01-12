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
    'Tor Error: ': 'Tor Error'
};

const SORT_CRITERIAS = ['http.status_code', 'error', 'version', 'tls.grade',
    'http.grade', 'html.grade', 'timing.initial', 'url'];

function getValue(f, obj, ...keys) {
    let value = obj;
    for(let i=0; i<keys.length; i++) {
        const k = keys[i];
        if (k === undefined) {
            break;
        }
        if ((value === undefined)
            || (!value.hasOwnProperty(k))) {
            value = undefined;
            break;
        }
        value = value[k];
    }
    if (value !== undefined && f !== null) {
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

function compareTool(a, b, f, ...keys) {
    const va = getValue(f, a, ...keys);
    const vb = getValue(f, b, ...keys);
    if (va === '' && vb !== '') {
        return 1;
    }
    if (vb === '' && va !== '') {
        return -1;
    }
    if (va === undefined && vb !== undefined) {
        return -1;
    }
    if (va !== undefined && vb === undefined) {
        return 1;
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
        const result = compareTool(nsva, nsvb, null, i);
        if (result !== 0) {
            return result;
        }
    }
    return 0;
}

const CompareFunctionCriterias = {
    'http.status_code': (a, b) => -compareTool(a, b, null, 'http', 'status_code'),
    'error': (a, b) => -compareTool(a, b, null, 'error'),
    'network.asn_privacy': (a, b) => compareTool(a, b, null, 'network', 'asn_privacy'),
    'version': (a, b) => compareVersion(a.version, b.version),
    'tls.grade': (a, b) => compareTool(a, b, normalizeGrade, 'tls', 'grade'),
    'html.grade': (a, b) => compareTool(a, b, normalizeGrade, 'html', 'grade'),
    'http.grade': (a, b) => compareTool(a, b, normalizeGrade, 'http', 'grade'),
    'timing.initial': (a, b) => -compareTool(a, b, null, 'timing', 'initial'),
    'timing.search_wp.server.median': (a, b) => -compareTool(a, b, null, 'timing', 'search_wp', 'server', 'median'),
    'timing.search_wp.all.median': (a, b) => -compareTool(a, b, null, 'timing', 'search_wp', 'all', 'median'),
    'url': (a, b) => -compareTool(a, b, null, 'url'),
};

function compareFunctionCompose(...criterias) {
    const criteriaFunctions = criterias.map((criteriaName) => CompareFunctionCriterias[criteriaName]);
    for (let i = 0; i < criteriaFunctions.length; i += 1) {
        if (typeof criteriaFunctions[i] !== 'function') {
            throw "criteria #" + i + " " + criterias[i] + " is not a function (" + criteriaFunctions[i] + ")";
        }
    }
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
    if (value === 'N/A') {
        value = 2;
    }
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
    if (grade === -1 || grade === '?') {
        return hslCss(0, 0, l + 20);
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
    if (typeof value === 'number') {
        return new Intl.NumberFormat('en', { maximumFractionDigits: 3, minimumFractionDigits: 3 }).format(value);
    } else {
        return value;
    }
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

function tooltip_add_timing(h, tooltip_lines, timing, time_label) {
    if (timing !== undefined) {
        const median = timing.median || timing.value;
        if (median !== undefined) {
            tooltip_lines.push(h('p', `${time_label}: ${formatResponseTime(median)}`));
        }
    }
}

Vue.component('url-component', {
    props: ['url', 'alternativeurls'],
    render: function(h) {
        if (this.url != null && this.url !== undefined) {
            let tooltipLines = [];
            if (this.alternativeurls !== undefined) {
                for (const altUrl of Object.keys(this.alternativeurls)) {
                    tooltipLines.push(h('tr', [
                        h('td', altUrl),
                    ]));
                }
            }
            const ahrefElement = h('a', { attrs: {  href: this.url } }, this.url);
            if (tooltipLines.length > 0) {
                return createTooltip(h,
                    ahrefElement,
                    [ h('table', tooltipLines) ]
                );
            } else {
                return ahrefElement;
            }
        }
    },
});

Vue.component('http-status-component', {
    props: ['value'],
    render: function (h) {
        if (this.value != null && this.value !== undefined) {
            const httpStatus = parseInt(this.value);
            let cssClass = '';
            if (httpStatus >= 200 && httpStatus < 300) {
                cssClass = 'label-success';
            } else if (httpStatus >= 300 && httpStatus < 400) {
                cssClass = 'label-warning';
            } else if (httpStatus >= 400 && httpStatus < 500) {
                cssClass = 'label-danger';
            } else if (httpStatus >= 500) {
                cssClass = 'label-danger';
            }
            return h('span', { staticClass: `label ${cssClass}` }, this.value);
        }
        return undefined;
    },
});

Vue.component('time-component', {
    props: ['value', 'time_select'],
    render: function (h) {
        if (this.value != null) {
            let successRate = 100;
            let value;
            let tooltip_lines;
            if (typeof (this.value) === 'object') {
                const timing = this.value[this.time_select];
                if (timing !== undefined) {
                    value = this.value[this.time_select].median;
                    if (value === undefined) {
                        value = this.value[this.time_select].value;
                    }
                    successRate = this.value.success_percentage;
                    tooltip_lines = [
                        h('p', `${successRate}% success`),
                    ];
                    tooltip_add_timing(h, tooltip_lines, this.value.all, 'Total time');
                    tooltip_add_timing(h, tooltip_lines, this.value.server, 'Server time');
                    tooltip_add_timing(h, tooltip_lines, this.value.load, 'Load time');
                    if (this.value.error !== undefined && this.value.error != 'Check failed') {
                        tooltip_lines.push(h('p', `Error: ${this.value.error}`));
                        if (value === undefined) {
                            value = 'N/A';
                        }
                    }
                }
            } else if (this.time_select === 'all') {
                value = this.value;
                tooltip_lines = null;
            }
            if (value !== undefined) {
                return createTooltip(h,
                    h('span', {
                        staticClass: 'value-responsetime',
                        attrs: {
                            style: `background-color:${hslResponseTime(value, successRate)}`,
                        },
                    }, formatResponseTime(value)), tooltip_lines);
            }
        }
        return undefined;
    },
});

Vue.component('engine-component', {
    props: ['instance', 'instance_url', 'engine'],
    render: function(h) {
        if (this.instance !== undefined && this.engine !== undefined) {
            const engine = this.instance.engines[this.engine];
            if (engine !== undefined) {
                const href= this.instance.url + 'search?q=!' + this.engine.replace(' ', '_') + ' time&theme=oscar&language=en';
                let staticClass = 'item-unknow';
                let text = '?';
                if (engine.status === true) {
                    staticClass = 'item-check';
                    text = '✔️';
                } else if (engine.status === false) {
                    staticClass = 'item-uncheck';
                    text = '❌';
                } else if (engine.stats === true) {
                    staticClass = 'item-maybe';
                    text = '🟡';
                }
                return createTooltip(h, h('a', {
                    staticClass: staticClass,
                    attrs: { href: href },
                }, text), engine.error);
            }
        }
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
                        let msg2;
                        if (unknownCountMin === 1) {
                            if (unknownInlineScriptCount == 1) {
                                msg2 = 'unique to this instance';
                            } else {
                                msg2 = 'at least one is unique to this instance';
                            }
                        } else {
                            msg2 = `at least one is used by ${unknownCountMin} instances`;
                        }
                        if (unknownCountMin >= 5) {
                            attrs.style = `background-color:${hslGradeHtml('B')}; color:white`;
                        } else if (unknownCountMin >= 2) {
                            attrs.style = `background-color:${hslGradeHtml('D')}; color:white`;
                        } else {
                            attrs.style = `background-color:${hslGradeHtml('E')}; color:white`;
                            msg2 = 'one only on this instance';
                        }
                        r.push(h('tr', [
                            h('td', { attrs: attrs }, ''),
                            h('td', { attrs: attrs }, `${msg}, ${msg2}`),
                            h('td', { attrs: attrs }, ''),
                        ]));
                    }
                    // external ressources
                    for (const ressourceType of ['iframe', 'script', 'style', 'link', 'other', 'img']) {
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
                                    extraInfo = '';
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
                                    let ressourceHRef = new URL(url, this.url).href;
                                    r.push(h('tr', [
                                        h('td', { attrs: attrs }, ressourceType),
                                        h('td', { attrs: attrs }, [
                                            h('a', { attrs: { href: ressourceHRef } }, ressourceHRef)
                                        ]),
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
                            certificate.issuer.organizationName || certificate.issuer.commonName,
                            ' (',
                            certificate.issuer.countryName,
                            ')',
                        ]), [
                        h('table', [
                            h('tr', [ h('td', [ h('b', [ 'Subject' ] ) ]) ]),
                            h('tr', [ h('td', 'Name'), h('td', certificate.subject.commonName) ]),
                            h('tr', [ h('td', 'AltName'), h('td', certificate.subject.altName) ]),
                            h('tr', [ h('td', 'Country'), h('td', certificate.subject.countryName) ]),
                            h('tr', [ h('td', 'Organization'), h('td', certificate.subject.organizationName)]),
                            h('tr', [ h('td', [ h('b', [ 'Issuer' ] ) ]) ]),
                            h('tr', [ h('td', 'Name'), h('td', certificate.issuer.commonName) ]),
                            h('tr', [ h('td', 'Country'), h('td', certificate.issuer.countryName) ]),
                            h('tr', [ h('td', 'Organization'), h('td', certificate.issuer.organizationName)]),
                            h('tr', [ h('td', [ h('b', [ 'Validity' ] ) ]) ]),
                            h('tr', [ h('td', 'From'), h('td', certificate.notBefore) ]),
                            h('tr', [ h('td', 'To'), h('td', certificate.notAfter) ]),
                            h('tr', [ h('td', [ h('b', [ 'Fingerprint' ] ) ]) ]),
                            h('tr', [ h('td', 'Serial number'), h('td', certificate.serialNumber) ]),
                            h('tr', [ h('td', 'SHA256'), h('td', certificate.sha256) ]),
                        ]),
                    ]);
            }
        }
        return undefined;
    },
});

Vue.component('ipv6-component', {
    props: ['value'],
    render: function (h) {
        if (this.value != null) {
            let text = '?';
            let grade = null;
            if (this.value.ipv6 === true) {
                text = 'Yes';
            }
            if (this.value.ipv6 === false) {
                text = 'No';
                grade = 'F-';
            }
            if (text !== null) {
                const attrs = {};
                if (grade !== null) {
                    attrs.style = `background-color:${hslGradeHtml(grade)}; color:white`;
                }
                return h('span', { class: 'value-ipv6', attrs: attrs }, text);
            }
        }
        return undefined;
    },
});

Vue.component('network-country-component', {
    props: ['value', 'asns'],
    render: function (h) {
        if ((this.value.ips != null) && Object.keys(this.value.ips).length > 0) {
            // element body
            const countries = Object.keys(this.value.ips).map((ip) => {
                const ipinfo = this.value.ips[ip];
                if (ipinfo !== undefined && ipinfo.asn != null) {
                    const ip_asn = this.asns[ipinfo.asn];
                    if (ip_asn !== undefined) {
                        let fieldValue = ip_asn.network_country;
                        if (fieldValue === null) {
                            fieldValue = ip_asn.asn_country_code;
                        }
                        return fieldValue;
                    }
                }
                return null;
            });
            const countryList = listUniq(countries.filter((v) => v !== null)).join(', ');
            return h('span', countryList);
        }
        return undefined;
    },
});

Vue.component('network-name-component', {
    props: ['value', 'asns'],
    render: function (h) {
        if ((this.value.ips != null) && Object.keys(this.value.ips).length > 0) {
            // element body
            const networks = Object.keys(this.value.ips).map((ip) => {
                const ipinfo = this.value.ips[ip];
                if (ipinfo !== undefined && ipinfo.asn != null) {
                    const ip_asn = this.asns[ipinfo.asn];
                    if (ip_asn !== undefined) {
                        let fieldValue = ip_asn.asn_description;
                        if (fieldValue === null) {
                            fieldValue = ip_asn.network_name;
                        }
                        return fieldValue;
                    }
                }
                return null;
            });
            const networksList = listUniq(networks.filter((v) => v !== null)).join(', ');
            // tooltip
            const reverseIpHosts = listUniq(Object.keys(this.value.ips).map((ip) => this.value.ips[ip].reverse || ip));
            const reverseIpHostElements = reverseIpHosts.map((host) => h('p', host));
            //
            let privacyGrade = undefined;
            switch (this.value.asn_privacy) {
                case -1:
                    privacyGrade = 'F-';
                    break;
                case 1:
                    privacyGrade = 'A+';
                    break;
            }
            const attrs = {};
            if (privacyGrade !== undefined) {
                attrs.style = `background-color:${hslGradeHtml(privacyGrade)}; color:white`;
            }
            return createTooltip(h, h('span', { class: 'value-network', attrs: attrs }, networksList), [reverseIpHostElements]);
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

function setComputedTimes(timing) {
    if (timing.server !== undefined && timing.all !== undefined) {
        timing.network = {
            'median': timing.all.median - timing.server.median || undefined,
            'value': timing.all.value - timing.server.value || undefined
        }
    }
    if (timing.load !== undefined && timing.server !== undefined) {
        timing.processing = {
            'median': timing.server.median - timing.load.median || undefined,
            'value': timing.server.value - timing.load.value || undefined
        }
    }
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
            ipv6: false,
            asn_privacy: false,
            network_name: '',
            network_country: '',
            google: false,
        },
        display: {
            time_select: 'all'
        },
        selected_tab: 'online_https',
        timestamp: undefined,
        instances: [],
        instances_nosearx: [],
        instances_ko: [],
        instances_tor: [],
        hashes: [],
        engines: {},
        categories: [],
        asns: {},
        selected_category: 'general',
    }),
    computed: {
        instances_filtered: function () {
            let result = this.instances;
            result = applyStrFilter(result, this.filters.version, (f, detail) => filterStartsWith(f, detail.version));
            result = applyStrFilter(result, this.filters.csp_grade, (f, detail) => filterIndexOf(f, detail.http.grade));
            result = applyStrFilter(result, this.filters.tls_grade, (f, detail) => filterIndexOf(f, detail.tls.grade));
            result = applyStrFilter(result, this.filters.html_grade,
                (f, detail) => filterIndexOf(f, detail.html.grade));
            result = applyStrFilter(result, this.filters.network_name,
                (f, detail) => {
                    for (const ipInfo of Object.values(detail.network.ips)) {
                        if (ipInfo.asn) {
                            const asn_info = this.asns[ipInfo.asn];
                            const network = asn_info.network_name || asn_info.asn_description || '';
                            return network.toLowerCase().indexOf(f) >= 0;
                        }
                    }
                    return false;
                });
            result = applyStrFilter(result, this.filters.network_country,
                (f, detail) => {
                    for (const ipInfo of Object.values(detail.network.ips)) {
                        if (ipInfo.asn) {
                            const asn_info = this.asns[ipInfo.asn]
                            const country = asn_info.network_country || asn_info.network_country || '';
                            return country.toLowerCase().indexOf(f) >= 0;
                        }
                    }
                    return false;
                });
            if (this.filters.ipv6) {
                result = result.filter((detail) => detail.network.ipv6 == true);
            }
            if (this.filters.asn_privacy) {
                result = result.filter((detail) => detail.network.asn_privacy >= 0);
            }
            if (this.filters.google) {
                result = result.filter((detail) => detail.timing.search_go.success_percentage > 0);
            }
            // sort
            const compareInstance = compareFunctionCompose(...SORT_CRITERIAS);
            result.sort(compareInstance);
            return result;
        },
        selected_engines: function() {
            let result = Object.keys(this.engines).filter((engine) => (this.engines[engine].categories.includes(this.selected_category)));
            result.sort();
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
                const instancesTor = [];
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
                    setComputedTimes(instance.timing.index);
                    setComputedTimes(instance.timing.search_wp);
                    setComputedTimes(instance.timing.search_go);

                    // dispatch instance
                    if (instance.error !== undefined) {
                        const errorKey = getErrorKey(instance.error);
                        setDefault(instancesWithError, errorKey, []);
                        instancesWithError[errorKey].push(instance);
                    } else {
                        if (instance.version !== null) {
                            if (instance.network_type == 'tor') {
                                instancesTor.push(instance)
                            } else {
                                instances.push(instance);
                            }
                        } else {
                            instancesWithoutSearx.push(instance);
                        }
                    }
                }

                const compareInstance = compareFunctionCompose(...SORT_CRITERIAS);
                instancesWithoutSearx.sort(compareInstance);
                for (const instanceList of Object.values(instancesWithError)) {
                    instanceList.sort(compareInstance);
                }
                instancesTor.sort(compareInstance);
                this.instances = instances;
                this.instances_ko = instancesWithError;
                this.instances_nosearx = instancesWithoutSearx;
                this.instances_tor = instancesTor;
                this.hashes = json.hashes;
                this.engines = json.engines;
                this.categories = json.categories;
                this.asns = json.asns;
                this.selected_category = this.categories[0];
            });
        });
    },
});
