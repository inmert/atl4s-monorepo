// Tab strip for switching between subviews of a single page (Robots vs.
// RobotDetail panes, ROS topic tabs, …). Controlled — pass the `active`
// id and an `onSelect` handler.

export interface SubnavItem {
  id: string;
  label: string;
}

export interface SubnavProps {
  items: SubnavItem[];
  active: string;
  onSelect: (id: string) => void;
}

export function Subnav({ items, active, onSelect }: SubnavProps) {
  return (
    <div className="subnav">
      {items.map((it) => (
        <a
          key={it.id}
          href="#"
          className={it.id === active ? 'active' : ''}
          onClick={(e) => {
            e.preventDefault();
            onSelect(it.id);
          }}
        >
          {it.label}
        </a>
      ))}
    </div>
  );
}
