declare module "../scripts/lib/snapshot-lib.mjs" {
  export function parseCapabilityGaps(markdown: string): any;
  export function parseFrontMatter(markdown: string): any;
  export function parseImplementationPhases(markdown: string): any;
  export function parseLoopState(markdown: string): any;
  export function parseTopology(containerTopologyMarkdown: string, serviceBoundariesMarkdown: string): any;
}
