interface Props {
  tone: "success" | "warning" | "error" | "info";
  children: string;
}

export function StatusChip({ tone, children }: Props) {
  return <span className={`chip ${tone}`}>{children}</span>;
}
