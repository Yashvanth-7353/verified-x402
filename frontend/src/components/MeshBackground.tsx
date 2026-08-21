/** Ambient, slow-drifting gradient mesh — sits behind every page via position:fixed. */
export function MeshBackground() {
  return (
    <div className="mesh-bg" aria-hidden="true">
      <div className="mesh-blob b1" />
      <div className="mesh-blob b2" />
      <div className="mesh-blob b3" />
    </div>
  );
}
