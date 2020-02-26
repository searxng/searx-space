'use strict';

let popperInstance = null;

function destroy() {
    if (popperInstance) {
        popperInstance.destroy();
        popperInstance = null;
    }
}

function create(element, tooltip) {
    if (popperInstance) {
        destroy();
    }
    popperInstance = Popper.createPopper(element, tooltip, {
        modifiers: [
        {
            name: 'offset',
            options: {
            offset: [0, 16],
            },
        },
        ],
    });
}

function initTooltip(element, tooltip) {
    let onTooltip = false;
    let onElement = false;

    function show() {
      tooltip.setAttribute('data-show', '');
      create(element, tooltip);
    }

    function hide() {
         setTimeout(function() {
            if (!onTooltip  && !onElement) {
              tooltip.removeAttribute('data-show');
              destroy();
            }
         }, 200);
    }

    const showEvents = ['mouseenter', 'focus'];
    const hideEvents = ['mouseleave', 'blur'];

    showEvents.forEach(event => {
      element.addEventListener(event, () => { onElement=true; show(); });
      tooltip.addEventListener(event, () => { onTooltip=true; show(); });
    });

    hideEvents.forEach(event => {
      element.addEventListener(event, () => { onElement=false; hide(); });
      tooltip.addEventListener(event, () => { onTooltip=false; hide(); });
    });
}

function init() {
    document.querySelectorAll('[data-tooltip]').forEach(element => {
        const tooltip_id = element.getAttribute('data-tooltip');
        const tooltip_content = document.getElementById(tooltip_id);
        if (tooltip_content !== null) {
            initTooltip(element, tooltip_content);
        }
    });
}

init();
