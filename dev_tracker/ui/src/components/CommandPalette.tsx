interface CommandItem {
  id: string;
  label: string;
  subtitle: string;
  description?: string;
  badge?: string;
  to: string;
}

interface Props {
  open: boolean;
  query: string;
  items: CommandItem[];
  onClose: () => void;
  onQueryChange: (value: string) => void;
  onSelect: (to: string) => void;
}

export function CommandPalette({ open, query, items, onClose, onQueryChange, onSelect }: Props) {
  if (!open) {
    return null;
  }

  return (
    <div className="command-overlay" onClick={onClose}>
      <div className="command-panel" onClick={(event) => event.stopPropagation()}>
        <div style={{ padding: "0.75rem" }}>
          <input
            className="input"
            autoFocus
            placeholder="Search routes and markdown context..."
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
          />
        </div>
        <ul className="command-list">
          {items.length === 0 ? (
            <li style={{ padding: "0.8rem", color: "var(--muted)" }}>No results.</li>
          ) : (
            items.map((item) => (
              <li key={item.id}>
                <button
                  className="command-item"
                  type="button"
                  onClick={() => {
                    onSelect(item.to);
                    onClose();
                  }}
                >
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", flexWrap: "wrap" }}>
                    <strong>{item.label}</strong>
                    {item.badge ? <span className="command-badge">{item.badge}</span> : null}
                  </div>
                  <div className="muted" style={{ fontSize: "0.82rem" }}>
                    {item.subtitle}
                  </div>
                  {item.description ? <div className="command-snippet">{item.description}</div> : null}
                </button>
              </li>
            ))
          )}
        </ul>
      </div>
    </div>
  );
}
