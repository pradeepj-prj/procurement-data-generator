declare module "react-cytoscapejs" {
  import type cytoscape from "cytoscape";
  import type { Component } from "react";

  interface CytoscapeComponentProps {
    elements: cytoscape.ElementDefinition[];
    stylesheet?: cytoscape.StylesheetCSS[];
    layout?: cytoscape.LayoutOptions;
    className?: string;
    cy?: (cy: cytoscape.Core) => void;
  }

  export default class CytoscapeComponent extends Component<CytoscapeComponentProps> {}
}
