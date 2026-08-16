interface PlainTextProps {
  children: string;
  className?: string;
}

/**
 * Administrator-entered prose, rendered as text.
 *
 * Announcement bodies and player biographies are plain text, and the newlines
 * an administrator typed are meaningful - a fixture list loses its shape
 * without them. `white-space: pre-wrap` (see .plain-text in index.css) keeps
 * every newline and run of spaces while still wrapping long lines and URLs
 * normally.
 *
 * The text goes in as a React child, so it is escaped. There is deliberately no
 * dangerouslySetInnerHTML here and no markdown step: nothing an administrator
 * types can become markup.
 */
export default function PlainText({ children, className }: PlainTextProps) {
  return <p className={className ? `plain-text ${className}` : "plain-text"}>{children}</p>;
}
