import ComponentWithTooltip from '../tooltip';

class TlsComponent extends ComponentWithTooltip {

    renderComponent(props) {
        return <>{ props.value.grade }</>;
    }

    renderTooltip(props) {
        return <a href={ props.value.gradeUrl }>{ props.value.version }</a>;
    }
}

export default TlsComponent;
