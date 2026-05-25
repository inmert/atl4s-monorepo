// Single import surface for the design primitives. Pages should:
//
//   import { Button, Card, StatTile } from '../lib/ui';
//
// Add new primitives here when you create them so the import path stays
// short. Styles for these components live in src/styles/primitives.css.

export { Badge } from './Badge';
export type { BadgeProps, Tone } from './Badge';

export { Button } from './Button';
export type { ButtonProps, ButtonVariant, ButtonSize } from './Button';

export { Card } from './Card';
export type { CardProps } from './Card';

export { Drawer } from './Drawer';
export type { DrawerProps } from './Drawer';

export { EmptyState } from './EmptyState';
export type { EmptyStateProps } from './EmptyState';

export { IconButton } from './IconButton';
export type { IconButtonProps } from './IconButton';

export { KeyValue } from './KeyValue';
export type { KeyValueProps } from './KeyValue';

export { Modal } from './Modal';
export type { ModalProps } from './Modal';

export { PageHeader } from './PageHeader';
export type { PageHeaderProps } from './PageHeader';

export { Pill } from './Pill';
export type { PillProps, PillTone } from './Pill';

export { Spinner } from './Spinner';
export type { SpinnerProps } from './Spinner';

export { StatTile } from './StatTile';
export type { StatTileProps, StatTone } from './StatTile';

export { StatusDot } from './StatusDot';
export type { StatusDotProps } from './StatusDot';

export { Subnav } from './Subnav';
export type { SubnavProps, SubnavItem } from './Subnav';

export { Toggle } from './Toggle';
export type { ToggleProps } from './Toggle';
