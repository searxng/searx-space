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

const GROUP_VERSION_PER_DAYS = 30;
const VERSION_START_DATE = new Date("2022-01-01").getTime();

const COMMON_ERROR_MESSAGE = {
    'Connection refused': 'Connection refused',
    'Connection timed out': 'Connection timed out',
    'HTTP status code 4': 'HTTP client error',
    'HTTP status code 5': 'HTTP server error',
    '[Errno -2] Name or service not known': 'Unknown host',
    '[Errno -2] Name does not resolve': 'Unknown host',
    'certificate verify failed': 'Certificate verify failed',
    'hostname \'': 'Hostname doesn\'t match certificate',
    'Tor Error: ': 'Tor Error',
    'Not configured as a public instance': 'Not configured as a public instance',
};

const SORT_CRITERIAS = [
    'http.status_code',
    'error',
    'timing.search.error',
    'timing.search_go.error',
    'version',
    'tls.grade',
    'http.grade',
    'html.grade',
    'timing.search.all',
    'url'
];

const HTML_GRADE_MAPPING = {
    'V': 3,
    'V, ?': 3,
    'V, js?': 3,

    'F': 3,
    'F, ?': 3,
    'F, js?': 3,

    'C': 3,
    'C, ?': 3,
    'C, js?': 3,

    'Cjs': 3,
    'Cjs, ?': 3,
    'Cjs, js?': 3,

    'E': 0,
    'E, ?': 0,
    'E, js?': 0,
    '👁️': 0,

    '?': -1,
    'js?': -1,
}

const HTML_GRADE_LABEL = {
    'V': 'Vanilla',
    'F': 'Fork',
    'C': 'Customized, vanilla Javascript',
    'Cjs': 'Customized, including Javascript',
    'E': 'External resources',
    '👁️': 'Analytics',
    '?': 'Unknow',
    'js?': 'Unloaded Javascript',
}

const DNSSEC_RESULT_TO_LABEL = {
    0: 'Unknow',
    1: 'Secure',
    2: 'Insecure',
    3: 'Bogus',
}
const DNSSEC_RESULT_TO_EMOJI = {
    0: '',
    1: '',
    2: '',
    3: ' ❗',
}


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
    const vdate = v.replaceAll("+", "-").split("-")[0].replaceAll('.', "-")
    const asDate = new Date(vdate);
    if (!isNaN(asDate)) {
        // version format "YYYY.MM.DD-HASH" (for example "2022.03.01-0ddcc124")
        // group version per month
        const relativeDate = asDate.getYear() * 12 + asDate.getMonth();
        const hash = v.split("-")[1];
        return [relativeDate, 0, 0, 0, hash];
    }
    // version format "MAJOR.MINOR.PATCH-DISTANCE-HASH" (for example "1.0.0-356-c9e6d9f5")
    const vdash = v.split(/[\-\+]/);
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

function normalizeHtmlGrade(grade) {
    if (grade === undefined || grade === null) {
        return -1;
    }
    const ngrade = HTML_GRADE_MAPPING[grade];
    if (ngrade === undefined) {
        return -1;
    }
    return ngrade;
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


function getTime(timing) {
    if (timing.value !== undefined) {
        return timing.value;
    }
    if (timing.median !== undefined) {
        return timing.median;
    }
    return undefined;
}

function isError(timing) {
    if (timing.success_percentage < 100) {
        return 100 - timing.success_percentage;
    }
    if (timing.error !== undefined) {
        return 100;
    }
    return 0;
}

const CompareFunctionCriterias = {
    'http.status_code': (a, b) => -compareTool(a, b, null, 'http', 'status_code'),
    'error': (a, b) => -compareTool(a, b, null, 'error'),
    'network.asn_privacy': (a, b) => compareTool(a, b, null, 'network', 'asn_privacy'),
    'version': (a, b) => compareVersion(a.version, b.version),
    'tls.grade': (a, b) => compareTool(a, b, normalizeGrade, 'tls', 'grade'),
    'html.grade': (a, b) => compareTool(a, b, normalizeHtmlGrade, 'html', 'grade'),
    'http.grade': (a, b) => compareTool(a, b, normalizeGrade, 'http', 'grade'),
    'timing.initial.all': (a, b) => -compareTool(a, b, getTime, 'timing', 'initial', 'all'),
    'timing.search.error': (a, b) => -compareTool(a, b, isError, 'timing', 'search'),
    'timing.search_go.error': (a, b) => -compareTool(a, b, isError, 'timing', 'search_go'),
    'timing.search.all': (a, b) => -compareTool(a, b, getTime, 'timing', 'search', 'all'),
    'timing.search_wp.all': (a, b) => -compareTool(a, b, getTime, 'timing', 'search_wp', 'all'),
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
    const responseTimeInPercentage = translateValue(value, 0.6, 2.5, 0, 100, true);
    const successRateNormalized = translateValue(successRate || 100, 70, 100, 0, 100, false);
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

function hslNormalizedGradeHtml(ngrade) {
    const l = 54;
    if (ngrade ===-1) {
        return hslCss(0, 0, l + 20);
    }
    const value = Math.min(3, Math.max(0, ngrade));
    const h = translateValue(value, 0, 3, 0, 128, false);
    const s = translateValue(value, 0, 3, 39, 54, true);
    return hslCss(h, s, l);
}

function hslGradeHtml(grade) {
    return hslNormalizedGradeHtml(normalizeHtmlGrade(grade));
}

function hslErrorPercentage(percentage) {
    const l = 54;
    const normalizedPercentage = 100 - Math.min(100, Math.max(0, percentage));
    const value = normalizedPercentage / 5;
    const h = translateValue(value, 0, 20, 0, 128, false);
    const s = translateValue(value, 0, 20, 39, 54, true);
    return hslCss(h, s, l);
}

function hslUptimePercentage(percentage) {
    const l = 54;
    const value1 = Math.min(100, Math.max(90, percentage)) - 90; // from 0 to 10
    const value = value1 * value1; // from 0 to 100
    const h = translateValue(value, 0, 100, 0, 128, false);
    const s = translateValue(value, 0, 100, 39, 54, true);
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
    props: ['url', 'alternativeurls', 'comments', 'git_url'],
    render: function(h) {
        if (this.url != null && this.url !== undefined) {
            let tooltipLines = [];
            if (this.comments !== undefined) {
                for (const comment of this.comments) {
                    tooltipLines.push(h('tr', [
                        h('td', comment),
                    ]));
                }
            }
            if (this.alternativeurls !== undefined && Object.keys(this.alternativeurls).length > 0) {
                if (this.comments !== undefined && this.comments.length > 0) {
                    tooltipLines.push(h('tr', [
                        h('td', ''),
                    ]));
                }
                for (const [altUrl, altComment] of Object.entries(this.alternativeurls)) {
                    tooltipLines.push(h('tr', [
                        h('td', altComment),
                        h('td', altUrl)
                    ]));
                }
            }
            tooltipLines.push(h('tr', [
                h('td', 'Git URL'),
                h('td', [ h('a', { attrs: { href: this.git_url } }, this.git_url) ]),
            ]));
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
            let tooltip_lines = [];
            const timing = this.value[this.time_select];
            if (timing !== undefined) {
                value = timing.median;
                if (value === undefined) {
                    value = timing.value;
                }
                successRate = this.value.success_percentage;
                if (successRate !== undefined) {
                    tooltip_lines.push(h('p', `${successRate}% success`));
                }
            }
            if (this.value.error !== undefined ) {
                tooltip_lines.push(h('p', `Error: ${this.value.error}`));
                if (value === undefined) {
                    value = 'Error';
                }
            }
            if (timing !== undefined) {
                tooltip_add_timing(h, tooltip_lines, this.value.all, 'Total time');
                tooltip_add_timing(h, tooltip_lines, this.value.server, 'Server time');
                tooltip_add_timing(h, tooltip_lines, this.value.load, 'Load time');
            }
            if (this.value.error === 'No result' && this.value.success_percentage === 0) {
                return undefined;
            }
            if (value == 'Error') {
                return createTooltip(h,
                    h('span', value),
                    tooltip_lines);
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
    props: ['instance', 'instance_url', 'engine', 'engine_errors'],
    render: function(h) {
        if (this.instance !== undefined && this.engine !== undefined) {
            const engine = this.instance.engines[this.engine];
            if (engine !== undefined) {
                const href= this.instance.url + 'search?q=!' + this.engine.replace(' ', '_') + ' time&language=en';

                let text;
                let working_engine = false;
                let checker_result = typeof engine.checker!=='undefined'?engine.checker.success:null;
                let error_rate = typeof engine.error_rate!=='undefined'?engine.error_rate:null;
                let engine_css_class;
                if (checker_result === null && error_rate === null) {
                    engine_css_class = 'unknow';
                } else if (error_rate >= 90) {
                    engine_css_class = 'error';
                } else if (checker_result === false || error_rate > 5) {
                    engine_css_class = 'warning';
                } else {
                    engine_css_class = 'ok';
                    working_engine = true;                        
                }
                text = [ h('span', { attrs: { 'class': engine_css_class } }, '') ];
                // data about stats/errors
                const tableTooltipContent = [];
                if (working_engine) {
                    const error_th_style = 'padding: 0.25rem; color: white; background-color:' + hslErrorPercentage(0);
                    tableTooltipContent.push(h('tr', [ h('th', { attrs: { 'colspan': 2, 'style': error_th_style } }, 'No error')]));
                } else if (error_rate !== null) {
                    const normalizedErrorRate = engine.error_rate || 0;
                    let error_th_style = 'padding: 0.25rem; color: white; background-color:' + hslErrorPercentage(normalizedErrorRate);
                    if ((normalizedErrorRate) === 0) {
                        error_th_style = 'padding: 0.25rem';
                    }
                    tableTooltipContent.push(h('tr',
                        [
                            h('th', { attrs: { 'scope': 'row', 'style': error_th_style } }, 'Error rate'),
                            h('th', { attrs: { 'scope': 'row', 'style': error_th_style } }, (normalizedErrorRate) + '%')
                        ])
                    );
                }

                if (engine.errors) {
                    for(const error_index of engine.errors) {
                        tableTooltipContent.push(h('tr', [ h('td', { attrs: { 'colspan': 2  } }, [ this.engine_errors[error_index]])]));
                    }
                }

                // data about stats/checker
                if (checker_result !== null) {
                    const checker_result_text = engine.checker.success ? 'pass':'fail'
                    const error_th_style = 'padding: 0.25rem; color: white; background-color:' + hslErrorPercentage(engine.checker.success ? 0:100);
                    tableTooltipContent.push(h('tr', [ h('td', { attrs: { 'colspan': 2  } }, '') ]));
                    tableTooltipContent.push(h('tr', [
                        h('th', { attrs: { 'scope': 'row', 'style': error_th_style } }, 'Checker'),
                        h('th', { attrs: { 'scope': 'row', 'style': error_th_style } }, checker_result_text)
                    ]));
                    for(const checker_error of engine.checker.errors) {
                        tableTooltipContent.push(h('tr', [ h('td', { attrs: { 'colspan': 2  } }, [ checker_error ])]));
                    }
                }

                let content = h('a', {
                    staticClass: 'engine-result',
                    attrs: { href: href },
                }, text);
                if (tableTooltipContent.length > 0) {
                    const tooltipContent = h('table', { attrs: {'class': 'engine-tooltip'} }, tableTooltipContent);
                    return createTooltip(h, content, [ tooltipContent ]);
                } else {
                    return content;
                }
                
            }
        }
    },
});

Vue.component('timestamp-component', {
    props: ['value'],
    template: '<time datetime="{{ new Date(value * 1000).toString() }}">{{ new Date(value * 1000).toString() }}</time>',
});

Vue.component('html-component', {
    props: ['value', 'hashes', 'url', 'git_url'],
    render: function (h) {
        if (this.value != null && this.value !== undefined) {
            // eslint-disable-next-line prefer-const
            let { grade, ressources } = this.value;
            const tooltip = [];
            if (ressources !== undefined && this.hashes != null && this.hashes !== undefined) {
                const r = [];
                const {  error } = ressources;
                if (ressources.script || ressources.style || ressources.inline_script) {
                    //
                    const grade_id = grade.split(',')[0];
                    let label = HTML_GRADE_LABEL[grade_id];
                    const attrs = {};
                    if (grade_id != 'F') {
                        r.push(h('tr', [
                            h('td', { attrs: attrs }, ''),
                            h('td', { attrs: attrs }, label),
                            h('td', { attrs: attrs }, ''),
                        ]));
                    }
                    r.push(h('tr', [
                        h('td', { attrs: attrs }, 'Git URL'),
                        h('td', { attrs: attrs }, [ h('a', { attrs: { href: this.git_url } }, this.git_url) ]),
                        h('td', { attrs: attrs }, ''),
                    ]));
                    // inline scripts
                    let unknownCountMin = 1000000;
                    let unknownInlineScriptCount = 0;
                    for (const ressourceDetail of ressources.inline_script) {
                        const ressourceHash = this.hashes[ressourceDetail.hashRef];
                        if (ressourceHash) {
                            if ('unknown' in ressourceHash) {
                                unknownInlineScriptCount += 1;
                                unknownCountMin = Math.min(unknownCountMin, ressourceHash.count);
                            }
                        }
                    }
                    if (unknownInlineScriptCount > 0) {
                        const attrs = {
                            style: `background-color:${hslNormalizedGradeHtml(1)}; color:white`
                        };
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
                                    attrs.style = `background-color:${hslNormalizedGradeHtml(0)}; color:white`;
                                } else if (ressourceDetail.notFetched) {
                                    addThisRessource = true;
                                    attrs.style = `background-color:${hslNormalizedGradeHtml(-1)}; color:white`;
                                    extraInfo = ressourceDetail.error;
                                } else if (ressourceHash) {
                                    extraInfo = '';
                                    if (ressourceHash.unknown) {
                                        addThisRessource = true;
                                        attrs.style = `background-color:${hslNormalizedGradeHtml(1)}; color:white`;
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
                    attrs.style = `background-color:${hslGrade(grade)}; color:white`;
                }
                return h('span', { class: 'value-ipv6', attrs: attrs }, text);
            }
        }
        return undefined;
    },
});

Vue.component('network-country-component', {
    props: ['value', 'cidrs'],
    render: function (h) {
        if ((this.value.ips != null) && Object.keys(this.value.ips).length > 0) {
            // element body
            const countries = Object.keys(this.value.ips).map((ip) => {
                const ipinfo = this.value.ips[ip];
                if (ipinfo !== undefined && ipinfo.asn_cidr != null) {
                    const asn_cidr = this.cidrs[ipinfo.asn_cidr];
                    if (asn_cidr !== undefined) {
                        let fieldValue = asn_cidr.network_country;
                        if (fieldValue === null) {
                            fieldValue = asn_cidr.asn_country_code;
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
    props: ['value', 'cidrs'],
    render: function (h) {
        if ((this.value.ips != null) && Object.keys(this.value.ips).length > 0) {
            // element body
            const networks = Object.keys(this.value.ips).map((ip) => {
                const ipinfo = this.value.ips[ip];
                if (ipinfo !== undefined && ipinfo.asn_cidr != null) {
                    const asn_cidr = this.cidrs[ipinfo.asn_cidr];
                    if (asn_cidr !== undefined) {
                        return asn_cidr.asn_description;
                    }
                }
                return null;
            });
            const networksList = listUniq(networks.filter((v) => v !== null)).join(', ');
            // tooltip
            let content = networksList + DNSSEC_RESULT_TO_EMOJI[this.value.dnssec];
            const dnssec = this.value.dnssec;
            const tooltipContent = [ ];
            tooltipContent.push(h('h5', content));
            if (dnssec > 0) {
                tooltipContent.push(h('p', [ h('b', 'DNSSEC') ]));
                tooltipContent.push(h('p', DNSSEC_RESULT_TO_LABEL[dnssec] + DNSSEC_RESULT_TO_EMOJI[dnssec]));
            }
            tooltipContent.push(h('p', [ h('b', 'Reverse DNS') ]));
            const reverseIpHosts = listUniq(Object.keys(this.value.ips).map((ip) => this.value.ips[ip].reverse || ip));
            for(const host of reverseIpHosts) {
                tooltipContent.push(h('p', host));
            }
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
                attrs.style = `background-color:${hslGrade(privacyGrade)}; color:white`;
            } else if (this.value.dnssec == 3) {
                attrs.style = `background-color:${hslGrade('D-')}; color:white`;
            }
            return createTooltip(h, h('span', { class: 'value-network', attrs: attrs }, content), [tooltipContent]);
        }
        return undefined;
    },
});

Vue.component('uptime-component', {
    props: ['value', 'url'],
    render: function (h) {
        if (this.value != null && this.value !== undefined) {
            const hostPath = new URL(this.url).host.replaceAll('.', '-');
            const attrs = {
                style: `background-color:${hslUptimePercentage(this.value.uptimeMonth)}; color:white`,
                href: "https://uptime.searxng.org/history/" + hostPath,
            };
            const element = h('a', { staticClass: 'value-uptime', attrs: attrs }, Math.round(this.value.uptimeMonth) + ' %');
            const tooltipContent = [
                h('table', {}, [
                    h('tr', {}, [
                        h('td', "Today"),
                        h('td', `${Math.round(this.value.uptimeDay)} %`)
                    ]),
                    h('tr', [
                        h('td', "This week"),
                        h('td', `${Math.round(this.value.uptimeWeek)} %`)
                    ]),
                    h('tr', [
                        h('td', "This month"),
                        h('td', `${Math.round(this.value.uptimeMonth)} %`)
                    ]),
                    h('tr', [
                        h('td', "This year"),
                        h('td', `${Math.round(this.value.uptimeYear)} %`)
                    ]),
                ])
            ];
            return createTooltip(h, element, tooltipContent);
        }
        return null;
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
            fork_select: '',
            version: '',
            html_grade: '',
            csp_grade: '',
            tls_grade: '',
            ipv6: false,
            asn_privacy: false,
            network_name: '',
            network_country: '',
            standard_search: false,
            engines: {

            },
            well_known_engines: true,
        },
        display: {
            time_select: 'all',
            comments: false,
        },
        selected_tab: 'online_https',
        timestamp: undefined,
        instances: [],
        instances_nosearx: [],
        instances_ko: [],
        instances_tor: [],
        forks: [],
        hashes: [],
        engines: {},
        engine_errors: [],
        categories: [],
        asns: {},
        selected_category: 'general',
    }),
    computed: {
        instances_filtered: function () {
            let result = this.instances;
            if (this.filters.fork_select != '') {
                result = result.filter((detail) => detail.git_url == this.filters.fork_select)
            }
            result = applyStrFilter(result, this.filters.version, (f, detail) => filterStartsWith(f, detail.version));
            result = applyStrFilter(result, this.filters.csp_grade, (f, detail) => filterIndexOf(f, detail.http.grade));
            result = applyStrFilter(result, this.filters.tls_grade, (f, detail) => filterIndexOf(f, detail.tls.grade));
            result = applyStrFilter(result, this.filters.html_grade,
                (f, detail) => filterIndexOf(f, detail.html.grade));
            result = applyStrFilter(result, this.filters.network_name,
                (f, detail) => {
                    for (const ipInfo of Object.values(detail.network.ips)) {
                        if (ipInfo.asn_cidr) {
                            const asn_cidr = this.cidrs[ipInfo.asn_cidr];
                            const network = asn_cidr.network_name || asn_cidr.asn_description || '';
                            return network.toLowerCase().indexOf(f) >= 0;
                        }
                    }
                    return false;
                });
            result = applyStrFilter(result, this.filters.network_country,
                (f, detail) => {
                    for (const ipInfo of Object.values(detail.network.ips)) {
                        if (ipInfo.asn_cidr) {
                            const asn_cidr = this.cidrs[ipInfo.asn_cidr]
                            const country = asn_cidr.network_country || asn_cidr.asn_country_code || '';
                            return country.toLowerCase().indexOf(f) >= 0;
                        }
                    }
                    return false;
                });
            for(let [engine_name, no_error] of Object.entries(this.filters.engines)) {
                if (no_error) {
                    result = result.filter((detail) => {
                        let engine_detail = detail.engines[engine_name];
                        if (engine_detail === undefined) {
                            return false;
                        }
                        if (engine_name == 'google' && detail.timing.search_go.success_percentage === 0) {
                            return false;
                        }
                        if (engine_detail['error_rate']) {
                            return engine_detail['error_rate'] <= 10;
                        }
                        if (engine_detail['checker'] && engine_detail['checker']['simple']) {
                            return engine_detail['checker']['simple'].length == 0;
                        }
                        return true;
                    })
                }
            }
            if (this.filters.ipv6) {
                result = result.filter((detail) => detail.network.ipv6 == true);
            }
            if (this.filters.asn_privacy) {
                result = result.filter((detail) => detail.network.asn_privacy >= 0);
            }
            if (this.filters.standard_search) {
                result = result.filter((detail) => detail.timing.search.success_percentage > 0);
            }
            // sort
            const compareInstance = compareFunctionCompose(...SORT_CRITERIAS);
            result.sort(compareInstance);
            return result;
        },
        selected_engines: function() {
            let result = Object.keys(this.engines).filter((engine) => (this.engines[engine].categories.includes(this.selected_category)));
            if (this.filters.well_known_engines) {
                result = result.filter(n => this.engines[n].stats.instance_count > 20);
            } else {
                result = result.filter(n => this.engines[n].stats.instance_count <= 20);
            }
            result = result.sort();
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
                    setDefault(instance.timing, 'initial', {});
                    setDefault(instance.timing.initial, 'all', {});
                    setDefault(instance.timing, 'search', {});
                    setDefault(instance.timing.search, 'all', {});
                    setDefault(instance.timing, 'search_wp', {});
                    setDefault(instance.timing.search_wp, 'all', {});
                    setDefault(instance.timing, 'search_go', {});
                    setDefault(instance.timing.search_go, 'all', {});
                    setDefault(instance, 'html', {});
                    setDefault(instance.html, 'grade', '');
                    setComputedTimes(instance.timing.search);
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
                this.forks = ['', ...json.forks.map(f => ({text: f, value:f}))];
                this.forks[1].text = 'Vanilla'
                this.display.fork_select = json.forks[0];
                this.hashes = json.hashes;
                this.engines = json.engines;
                this.engine_errors = json.engine_errors;
                this.categories = json.categories;
                this.cidrs = json.cidrs;
                this.selected_category = this.categories[0];
                for(const engine_name of Object.keys(json.engines)) {
                    this.filters[engine_name] = false;
                }
            });
        });
    },
});
