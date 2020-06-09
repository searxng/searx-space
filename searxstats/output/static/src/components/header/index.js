import { Link } from 'preact-router/match';


const Header = () => (
	<nav className="navbar navbar-dark bg-dark shadow-sm navbar-expand-lg navbar-expand">
		<a className="navbar-brand" href="#">Searx instances</a>
		<button class="navbar-toggler" type="button" data-toggle="collapse" data-target="#navbarCollapse" aria-controls="navbarCollapse" aria-expanded="false" aria-label="Toggle navigation">
      		<span class="navbar-toggler-icon"></span>
    	</button>
		<div className="collapse navbar-collapse" id="navbarSupportedContent">
			<ul className="navbar-nav mr-auto">
				<li className="nav-item" activeClassName="active"><Link href="/" className="nav-link">Online HTTPS</Link></li>
				<li className="nav-item" activeClassName="active"><Link href="/tor" className="nav-link">Online Tor</Link></li>
				<li className="nav-item" activeClassName="active"><Link href="/offline" className="nav-link">Offline &amp; error</Link></li>
				<li className="nav-item" activeClassName="active"><Link href="/engines" className="nav-link">Engines</Link></li>
				<li className="nav-item" activeClassName="active"><Link href="/about" className="nav-link">About</Link></li>
			</ul>
		</div>
	</nav>
);

export default Header;
