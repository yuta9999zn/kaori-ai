// Moddle extension so bpmn-js serialises Kaori's `kaori:nodeType` attribute
// onto BPMN flow elements (tasks/events/gateways). Without this, the modeler
// would drop the unknown-namespace attribute on export and the BE mapper
// (parse_bpmn_xml) could never read which Kaori action a task carries.
//
// Mirrors the attribute the catalog + BE expect: KAORI_NODETYPE_ATTR.
export const kaoriModdle = {
  name: 'Kaori',
  uri: 'http://kaori.ai/bpmn',
  prefix: 'kaori',
  xml: { tagAlias: 'lowerCase' },
  associations: [],
  types: [
    {
      name: 'KaoriExtension',
      // Attach to every flow element so a Task/Event/Gateway can carry it.
      extends: ['bpmn:FlowElement'],
      properties: [
        { name: 'nodeType', isAttr: true, type: 'String' },
      ],
    },
  ],
} as const;
