/**
 * Bootstrap Icons wrapper.
 * Usage: <Icon name="check-circle" style={{ fontSize: 16 }} />
 */
export function Icon({ name, style }) {
  return <i className={`bi bi-${name}`} style={style} />;
}
