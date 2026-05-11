import { useTracker } from "../lib/tracker-context";
import { GlassPopover } from "./GlassPopover";

interface TooltipHintProps {
  text: string;
  label?: string;
}

export function TooltipHint({ text, label = "More info" }: TooltipHintProps) {
  const { settings } = useTracker();

  if (!settings.tooltipsEnabled || !text.trim()) {
    return null;
  }

  return (
    <GlassPopover
      ariaLabel={`${label}: ${text}`}
      openOnHover
      preferredWidth={260}
      triggerClassName="tooltip-hint"
      trigger={<span>?</span>}
    >
      <div className="tooltip-popover-copy">
        <p style={{ margin: 0 }}>{text}</p>
      </div>
    </GlassPopover>
  );
}
