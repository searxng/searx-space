# searx-space

Statistics on the [searx](https://searx.github.io/searx/) instances: https://searx.space ([Onion URL](http://searxspbitokayvkhzhsnljde7rqmn7rvoga6e4waeub3h7ug3nghoad.onion/))

## Installation

### Download and run cryptcheck-backend

searx-space expects [cryptcheck-backend](https://github.com/dalf/cryptcheck-backend) to respond on localhost:7000:

```sh
docker run --rm -p 7000:7000 dalf/cryptcheck-backend:latest
```

Note: cryptcheck-backend is used to get the TLS grade.

### Install system packages

Install packages (for Ubuntu):

```sh
apt install firefox wget git build-essential python3-dev virtualenv python3-virtualenv libxslt-dev zlib1g-dev libffi-dev libssl-dev libyaml-dev python3-ldns python3-venv tor
```

For Debian, `firefox` should be replaced with `firefox-esr`.

### Get the project

Install searxstats:

```sh
cd /usr/local
sudo git clone https://github.com/searxng/searx-space
sudo useradd searxstats -d /usr/local/searx-space
sudo chown searxstats:searxstats -R /usr/local/searx-space
```

### Project install

```sh
sudo -u searxstats -i
cd /usr/local/searx-space
python3 -m venv --system-site-packages ve
. ./ve/bin/activate
pip install -r requirements.txt
./utils/install-geckodriver
mkdir cache
mkdir html/data
touch html/data/instances.json
```

### Run

Run (it takes between 30 minutes and 1 hour):

```sh
python3 -m searxstats --cache /usr/local/searx-space/cache --all
```

Output in `html/data/instances.json`.

To display all options:

```sh
python3 -m searxstats --help
```
