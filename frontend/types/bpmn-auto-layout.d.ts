// bpmn-auto-layout ships no types. layoutProcess takes BPMN 2.0 XML and
// returns XML with freshly generated DI (positions / waypoints / labels).
declare module 'bpmn-auto-layout' {
  export function layoutProcess(xml: string): Promise<string>;
}
