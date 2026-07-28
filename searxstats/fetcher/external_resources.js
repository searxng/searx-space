function fetchResourceHashes() {
    'use strict';

    const allResources = { };
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

    function resource_hash_subtle(textBuffer) {
        return new Promise((resolutionFunc,rejectionFunc) => {
            crypto.subtle.digest('SHA-256', textBuffer).then((hashBuffer) => {
                resolutionFunc(bufferToHex(hashBuffer));
            }).catch((error) => {
                rejectionFunc(error);
            });
        });
    }

    function resource_hash_fallback(textBuffer) {
        return new Promise((resolutionFunc,rejectionFunc) => {
            try {
                resolutionFunc(bufferToHex(window.sha256.hash(textBuffer)));
            } catch(error) {
                rejectionFunc(error.toString());
            }
        });
    }

    // Use the Javascript implementation by default (http:// websites)
    let resource_hash = resource_hash_fallback;
    if ("crypto" in window && "subtle" in window.crypto) {
        // Use native implementation (available only for https:// websites)
        resource_hash = resource_hash_subtle;
    }

    function addInlineResource(key, text) {
        // Encode as (utf-8) Uint8Array
        const textBuffer = new TextEncoder().encode(text);

        resource_hash(textBuffer).then((hash) => {
            allResources[key].push({hash});
        })
    }

    function addInlineResourceFromTags(key, tagName) {
        const elements = document.getElementsByTagName(tagName);
        if (typeof allResources[key] === 'undefined') {
            allResources[key] = [];
        }
        for (let i = 0; i < elements.length; i += 1) {
            const s = elements[i];
            const text = s.text;
    
            if (typeof text === 'string' && text.length > 0) {
                addInlineResource(key, text);
            }
        }
    }

    function fetchExternalResource(relativeUrl, initiatorType, url) {
        const catchNetworkError = (error) => {
            if (typeof error == 'Error') {
                error = error.toString();
            }
            // the resource has NOT been fetched
            allResources[initiatorType][relativeUrl].error = error || 'error';
        };
        const catchInternalError = (error) => {
            // the resource has been fetched
            delete allResources[initiatorType][relativeUrl].notFetched;
            allResources[initiatorType][relativeUrl].error = error;
        };

        fetch(url, fetchOptions)
            .then((response) => {
                if (response.ok) {
                    return response.arrayBuffer()
                        .then((buffer) => {
                            resource_hash(new Uint8Array(buffer)).then((hash) => {
                                if (typeof hash !== 'undefined') {
                                    allResources[initiatorType][relativeUrl].hash = hash;
                                    delete allResources[initiatorType][relativeUrl].notFetched;
                                }
                            }).catch(catchInternalError);
                        })
                        .catch(catchInternalError);
                }
                catchNetworkError(`HTTP status ${response.status}: ${response.statusText}`);
            })
            .catch(catchNetworkError);
    }

    // External resources
    performance.getEntriesByType('resource').forEach((r) => {
        // key is by default the URL of the resource (r.name)
        // notFetched is removed once the resource has been fetched
        let key = r.name;
        const value = {
            notFetched: true,
        };
        // lazy init of allResources[r.initiatorType]
        if (typeof allResources[r.initiatorType] === 'undefined') {
            allResources[r.initiatorType] = {};
        }
        // external if the URL is not a subpath of the document URL
        if (r.name.startsWith(document.URL)) {
            key = r.name.substring(document.URL.length);
        } else {
            value.external = true;
        }
        // set
        allResources[r.initiatorType][key] = value;
        // HTTP fetch of the resource to get the hash
        fetchExternalResource(key, r.initiatorType, r.name);
    });

    // Inline scripts and style
    addInlineResourceFromTags('inline_script', 'script');
    addInlineResourceFromTags('inline_style', 'style');

    // set getter function
    window.getResourceHashes = () => {
        const scripts = allResources.script;
        if (typeof scripts !== 'undefined') {
            for (const resource of Object.values(scripts)) {
                // no error, still to fetch: wait more
                if (typeof resource.notFetched !== 'undefined' && typeof resource.error === 'undefined') {
                    return null;
                }
            }
        }

        return allResources;
    };

    return 'return getResourceHashes()';
}
return fetchResourceHashes();
