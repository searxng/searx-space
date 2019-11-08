function fetchRessourceHashes() {
    'use strict';

    const DIGEST_ALGORITHM = 'SHA-256';
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

    function addInlineRessource(key, text) {
        // Encode as (utf-8) Uint8Array
        const textBuffer = new TextEncoder().encode(text);

        // hash
        crypto.subtle.digest(DIGEST_ALGORITHM, textBuffer).then((hashBuffer) => {
            allRessources[key].push({
                hash: bufferToHex(hashBuffer),
            });
        });
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
                            crypto.subtle.digest(DIGEST_ALGORITHM, buffer)
                                .then((hashBuffer) => {
                                    if (typeof hashBuffer !== 'undefined') {
                                        allRessources[initiatorType][relativeUrl].hash = bufferToHex(hashBuffer);
                                        delete allRessources[initiatorType][relativeUrl].notFetched;
                                    }
                                })
                                .catch(catchInternalError);
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
