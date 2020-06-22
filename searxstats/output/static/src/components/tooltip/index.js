import { createRef, Component } from 'preact';
import { usePopper } from 'react-popper';
import './style.css';

class TooltipComponent extends Component {

    state = {
        popperElement: null,
    }

    render(props, state) {
        if (props.referenceElement && props.children) {
            const { styles, attributes } = usePopper(props.referenceElement, state.popperElement, {
                modifiers: [{ 
                  placement: 'bottom-start',
                  strategy: 'fixed',
                  modifiers: [{
                        name: 'offset',
                        options: {
                          offset: [30, 5],
                        },
                      }]
                  }],
            });
            return <div className='tooltip' ref={state.popperElement} style={styles.popper} {...attributes.popper}>
                    { props.children }
                </div>;
        }
    }

}

class ComponentWithTooltip extends Component {
    state = {
        tooltipDisplayed: false,
    }

    showTooltip = () => {
        this.setState({ tooltipDisplayed: true, });
    }

    hideTooltip = () => {
        this.setState({ tooltipDisplayed: false, });
    }

    toogleTooltip = () => {
        this.setState({ tooltipDisplayed: !this.state.tooltipDisplayed, });
    }

    render(props, state) {
        const component = this.renderComponent(props, state);
        let children = component;
        if (state.tooltipDisplayed) {
            children = <>
                { component }
                { 'true' }
                <TooltipComponent referenceElement={component}>{ this.renderTooltip(props) }</TooltipComponent>
            </>;
        }

        return <span onFocus={this.showTooltip} onBlur={this.hideTooltip} onClick={this.toogleTooltip}
                     onTouchStart={this.toogleTooltip} onMouseEnter={this.showTooltip} onMouseLeave={this.hideTooltip}>
            { children }
        </span>;
    }

    renderComponent(props, state) {
        return <span></span>;
    }

    renderTooltip(props) {
        return <span>Dummy tooltip</span>;
    }
}

export default ComponentWithTooltip;