declare module 'react-cytoscapejs' {
  import type { ComponentType, CSSProperties } from 'react';
  import type { Core, ElementDefinition, LayoutOptions, StylesheetStyle } from 'cytoscape';
  interface Props {
    elements: ElementDefinition[];
    stylesheet?: StylesheetStyle[];
    layout?: LayoutOptions;
    style?: CSSProperties;
    cy?: (cy: Core) => void;
    wheelSensitivity?: number;
  }
  const CytoscapeComponent: ComponentType<Props> & {
    normalizeElements: (els: { nodes: ElementDefinition[]; edges: ElementDefinition[] }) => ElementDefinition[];
  };
  export default CytoscapeComponent;
}
