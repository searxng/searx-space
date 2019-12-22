# searx-stats2

Statistics on [searx](https://asciimoo.github.io/searx/) instances

## Example

https://searx.space/instances/

## Installation

Install packages:
```
apt install firefox wget git build-essential python3-dev virtualenv python3-virtualenv libxslt-dev zlib1g-dev libffi-dev libssl-dev libyaml-dev
```

Install searxstats:
```
cd /usr/local
sudo git clone https://github.com/dalf/searx-stats2
sudo useradd searxstats -d /usr/local/searx-stats2
sudo chown searxstats:searxstats -R /usr/local/searx-stats2
```

Install dependencies in a virtualenv:
```
sudo -u searxstats -i
cd /usr/local/searx-stats2
virtualenv -p $(which python3) ve
. ./ve/bin/activate
pip3 install -r requirements.txt
./utils/install-geckodriver
mkdir cache
mkdir html/data
```

Run (it takes about 1 hour):
```
python3 -m searxstats --cache /usr/local/searx-stats2/cache --all
```

Output in the ```html/data/instance.json``` directory.
