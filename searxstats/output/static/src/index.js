if (process.env.NODE_ENV === 'development') {
    require('preact/debug');
}

import 'bootstrap/dist/css/bootstrap.min.css';
import './style';
import App from './components/app';

export default App;
