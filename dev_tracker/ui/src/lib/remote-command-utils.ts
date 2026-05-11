function normalizePathSegment(value: string): string {
  return value.trim().replace(/^\/+|\/+$/g, "");
}

function quoteShellValue(value: string): string {
  return `'${value.replaceAll("'", `'\\''`)}'`;
}

function joinRemotePath(...segments: string[]): string {
  return segments.map((segment) => normalizePathSegment(segment)).filter(Boolean).join("/");
}

export function buildRemoteListCommand(targetRepo = ""): string {
  const normalizedRepo = normalizePathSegment(targetRepo);
  return normalizedRepo ? `ls -- ${quoteShellValue(normalizedRepo)}` : "ls";
}

export function buildRemoteSidecarCheckCommand(targetRepo: string, sidecarDir = ".moradins-harness"): string {
  const remotePath = joinRemotePath(targetRepo, sidecarDir || ".moradins-harness");
  return `ls -- ${quoteShellValue(remotePath || ".moradins-harness")}`;
}
