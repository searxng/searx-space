#!/bin/bash

git clone https://github.com/asciimoo/searx.git

rm -f hashes_raw.txt
touch hashes_raw.txt

cd searx

# FIXME load previous version, and stop parsing where the last run stoped
for commitid in $(git log --pretty=format:"%H"); do
	echo $commitid
	git checkout $commitid
	find searx/static -type f | xargs -d '\n' sha256sum | grep -v "./less" | cut -f1 -d\  | sort | uniq >> ../hashes_raw.txt
done

git checkout master

cd ..

# FIXME store last commit
sort hashes_raw.txt | uniq > hashes.txt
awk 'BEGIN { print "well_known_hashes = {" } { print "\"" $0 "\"," } END { print "}" }' hashes.txt > well_kown_hashes.py

rm hashes_raw.txt hashes.txt
