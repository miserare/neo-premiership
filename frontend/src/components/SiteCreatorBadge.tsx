/** Persisted public identity marker. Text remains visible because an icon,
 * colour or tooltip alone would not be an accessible label. */
export default function SiteCreatorBadge() {
  return (
    <span className="creator-badge" aria-label="Site Creator">
      <span aria-hidden="true">◆</span> Site Creator
    </span>
  );
}
