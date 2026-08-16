import { useId, useState } from "react";

interface DisclosureProps {
  /** Button text while collapsed - say what will appear, and how much of it. */
  showLabel: string;
  /** Button text while expanded. */
  hideLabel: string;
  children: (expanded: boolean) => React.ReactNode;
  className?: string;
}

/**
 * A show/hide control.
 *
 * A real `<button>`, so it is focusable, activates on Enter and Space, and is
 * announced as a button - none of which a clickable `<div>` would do.
 * `aria-expanded` and `aria-controls` tell assistive technology what state it
 * is in and what it governs.
 *
 * The children are a render function taking `expanded` rather than a fixed
 * element, because the collapsed state here is a *shorter* view of the same
 * data, not an empty one - which is also why nothing is refetched when it
 * opens.
 */
export default function Disclosure({
  showLabel,
  hideLabel,
  children,
  className,
}: DisclosureProps) {
  const [expanded, setExpanded] = useState(false);
  const contentId = useId();

  return (
    <div className={className}>
      <div id={contentId}>{children(expanded)}</div>
      <button
        type="button"
        className="disclosure__toggle"
        aria-expanded={expanded}
        aria-controls={contentId}
        onClick={() => setExpanded((open) => !open)}
      >
        {expanded ? hideLabel : showLabel}
      </button>
    </div>
  );
}
