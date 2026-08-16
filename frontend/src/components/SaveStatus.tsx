interface SaveStatusProps {
  success: string | null;
  /** Omit on a page with several forms: the error belongs next to the control
   * that produced it, not repeated at the top. */
  error?: string | null;
}

/**
 * The result of the last save.
 *
 * Success goes in a polite live region so a screen reader announces it without
 * interrupting; failures use role="alert", which is assertive, because the
 * administrator's change did not happen and they need to know now.
 *
 * Both regions are always in the DOM. A live region that is added at the same
 * moment as its text is frequently not announced at all - the region has to
 * exist first, and its content change is what gets read.
 */
export default function SaveStatus({ success, error = null }: SaveStatusProps) {
  return (
    <>
      <p className="save-status save-status--success" role="status" aria-live="polite">
        {success ?? ""}
      </p>
      {error && (
        <p className="save-status save-status--error" role="alert">
          {error}
        </p>
      )}
    </>
  );
}
