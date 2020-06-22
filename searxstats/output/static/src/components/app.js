/* eslint-disable quote-props */
import { h, Component } from 'preact';
import { Router } from 'preact-router';
import { Provider } from '@preact/prerender-data-provider';
import Header from './header';

// Code-splitting is automated for routes
import Online from '../routes/online';
import Offline from '../routes/offline';
import About from '../routes/about';

const Error = ({ type, url }) => (
	<section class="error">
		<h2>Error {type}</h2>
		<p>It looks like we hit a snag.</p>
		<pre>{url}</pre>
	</section>
);

class App extends Component {

	/** Gets fired when the route changes.
	 *	@param {Object} event		"change" event from [preact-router](http://git.io/preact-router)
	 *	@param {string} event.url	The newly routed URL
	 */
	handleRoute = e => {
		this.currentUrl = e.url;
	};

	render(props, state) {
		console.log(state);
		return (			
			<Provider value={props}>
				<Header />
				<div class="container-fluid">
					<Router onChange={this.handleRoute}>
						<Online path="/" />
						<Offline path="/offline/" user="me" />
						<About path="/about" />
						<Error type="404" default />
					</Router>
				</div>
			</Provider>
		);
	}
}

export default App;
