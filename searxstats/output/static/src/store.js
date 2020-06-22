import createStore from 'unistore'
import { connect } from 'unistore/preact'

const initialStore = {
    version: '',
    tls_grade: '',
    csp_grade: '',
    html_grade: '',
    ipv6: false,
    asn_privacy: false,
    query: false,
    query_google: false
};

const store = createStore(initialStore);

const actions = store => ({

    setVersion: (_, newVersion) => { return { version: newVersion } },
    setTlsGrade: (_, newTlsGrade) => { return { tls_grade: newTlsGrade } },
    setCspGrade: (_, newCspGrade) => { return { csp_grade: newCspGrade } },
    setHtmlGrade: (_, newHtmlGrade) => { return { html_grade: newHtmlGrade } },

});

const connectToStore = (e) => connect(Object.keys(initialStore), actions)(e);

export { store, actions, connectToStore };
