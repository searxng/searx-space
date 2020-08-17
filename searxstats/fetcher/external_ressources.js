function fetchRessourceHashes() {
    'use strict';

    const allRessources = { };
    const fetchOptions = {
        method: 'GET',
        mode: 'cors',
        cache: 'default',
    };

    function bufferToHex(hashBuffer) {
        // Convert buffer to byte array
        const hashArray = Array.from(new Uint8Array(hashBuffer));

        // Convert bytes to hex string
        return hashArray.map((b) => b.toString(16).padStart(2, '0')).join('');
    }

    function resssource_hash_subtle(textBuffer) {
        return new Promise((resolutionFunc,rejectionFunc) => {
            crypto.subtle.digest('SHA-256', textBuffer).then((hashBuffer) => {
                resolutionFunc(bufferToHex(hashBuffer));
            }).catch((error) => {
                rejectionFunc(error);
            });
        });
    }

    function resssource_hash_fallback(textBuffer) {
        return new Promise((resolutionFunc,rejectionFunc) => {
            try {
                resolutionFunc(bufferToHex(window.sha256.hash(textBuffer)));
            } catch(error) {
                rejectionFunc(error.toString());
            }
        });
    }

    // Use the Javascript implementation by default (http:// websites)
    let ressource_hash = resssource_hash_fallback;
    if ("crypto" in window && "subtle" in window.crypto) {
        // Use native implementation (available only for https:// websites)
        ressource_hash = resssource_hash_subtle;
    }

    function addInlineRessource(key, text) {
        // Encode as (utf-8) Uint8Array
        const textBuffer = new TextEncoder().encode(text);

        ressource_hash(textBuffer).then((hash) => {
            allRessources[key].push({hash});
        })
    }

    function addInlineRessourceFromTags(key, tagName) {
        const elements = document.getElementsByTagName(tagName);
        if (typeof allRessources[key] === 'undefined') {
            allRessources[key] = [];
        }
        for (let i = 0; i < elements.length; i += 1) {
            const s = elements[i];
            const text = s.text;
    
            if (typeof text === 'string' && text.length > 0) {
                addInlineRessource(key, text);
            }
        }
    }

    function fetchExternalRessource(relativeUrl, initiatorType, url) {
        const catchNetworkError = (error) => {
            if (typeof error == 'Error') {
                error = error.toString();
            }
            // the ressource has NOT been fetched
            allRessources[initiatorType][relativeUrl].error = error || 'error';
        };
        const catchInternalError = (error) => {
            // the ressource has been fetched
            delete allRessources[initiatorType][relativeUrl].notFetched;
            allRessources[initiatorType][relativeUrl].error = error;
        };

        fetch(url, fetchOptions)
            .then((response) => {
                if (response.ok) {
                    return response.arrayBuffer()
                        .then((buffer) => {
                            ressource_hash(new Uint8Array(buffer)).then((hash) => {
                                if (typeof hash !== 'undefined') {
                                    allRessources[initiatorType][relativeUrl].hash = hash;
                                    delete allRessources[initiatorType][relativeUrl].notFetched;
                                }
                            }).catch(catchInternalError);
                        })
                        .catch(catchInternalError);
                }
                catchNetworkError(`HTTP status ${response.status}: ${response.statusText}`);
            })
            .catch(catchNetworkError);
    }

    // External ressources
    performance.getEntriesByType('resource').forEach((r) => {
        // key is by default the URL of the ressource (r.name)
        // notFetched is removed once the ressource has been fetched
        let key = r.name;
        const value = {
            notFetched: true,
        };
        // lazy init of allRessources[r.initiatorType]
        if (typeof allRessources[r.initiatorType] === 'undefined') {
            allRessources[r.initiatorType] = {};
        }
        // external if the URL is not a subpath of the document URL
        if (r.name.startsWith(document.URL)) {
            key = r.name.substring(document.URL.length);
        } else {
            value.external = true;
        }
        // set
        allRessources[r.initiatorType][key] = value;
        // HTTP fetch of the ressource to get the hash
        fetchExternalRessource(key, r.initiatorType, r.name);
    });

    // Inline scripts and style
    addInlineRessourceFromTags('inline_script', 'script');
    addInlineRessourceFromTags('inline_style', 'style');

    // set getter function
    window.getRessourceHashes = () => {
        const scripts = allRessources.script;
        if (typeof scripts !== 'undefined') {
            for (const ressource of Object.values(scripts)) {
                // no error, still to fetch: wait more
                if (typeof ressource.notFetched !== 'undefined' && typeof ressource.error === 'undefined') {
                    return null;
                }
            }
        }

        return allRessources;
    };

    return 'return getRessourceHashes()';
}
return fetchRessourceHashes();
