if (process.env.NODE_ENV === 'development') {
    require('preact/debug');
}

import 'bootstrap/dist/css/bootstrap.min.css';
import './style';
import App from './components/app';

import { Provider } from 'unistore/preact'
import { store, connectToStore } from './store';

const AppConnected = connectToStore(store)((store) => (
    <App></App>
));

const AppWithStore = () => (
    <Provider store={store}>
        <App></App>
    </Provider>
)

export default AppWithStore;
